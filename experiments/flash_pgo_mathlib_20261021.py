#!/usr/bin/env python3
"""Source-pinned, same-input PGO profile transfer experiment for the Soko-derived Flash research line.

Baseline: PGO trained on Init.Prelude; candidate: PGO trained on full pinned Mathlib.
Neither alters the type checker source, reductions, validation, or exit codes.
This is NOT an independent Nucleus experiment, nor an official PMU measurement.
"""
import hashlib
import json
import os
import pathlib
import statistics
import subprocess
import sys
import time

if len(sys.argv) != 4:
    raise SystemExit("usage: script.py portable196_root exact_mathlib.ndjson output_dir")
portable = pathlib.Path(sys.argv[1])
mathlib = pathlib.Path(sys.argv[2])
out = pathlib.Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
EXPECTED_SHA = "22c5de83469408950005589a3bc5ef5157c65549b5a802f85d567c29151306a6"
h = hashlib.sha256()
with mathlib.open("rb") as stream:
    for buf in iter(lambda: stream.read(4 << 20), b""):
        h.update(buf)
assert mathlib.stat().st_size == 6184415052, mathlib.stat().st_size
assert h.hexdigest() == EXPECTED_SHA, h.hexdigest()

bins = {
    "init_pgo": pathlib.Path("/tmp/flash-profile-init"),
    "mathlib_pgo": pathlib.Path("/tmp/flash-profile-mathlib")
}
assert all(p.is_file() for p in bins.values())
for name, path in bins.items():
    print("PROFILE_BINARY=" + json.dumps({"name":name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}), flush=True)
opts = ["--stdin", "--nat-extension", "--string-extension", "--axiom-allow-all", "--threads", "4"]
cases = [(kind, p) for kind in ("good","bad")
         for p in sorted((portable/kind).rglob("*.ndjson"))]
assert sum(g=="good" for g,_ in cases)==125 and sum(g=="bad" for g,_ in cases)==71
verdicts = []
for group, path in cases:
    row = {"case":str(path.relative_to(portable)),"expected":group,
           "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    for arm, binary in bins.items():
        with path.open("rb") as src:
            p = subprocess.run([str(binary), *opts], stdin=src, capture_output=True, timeout=90)
        row[arm] = p.returncode
        assert p.returncode in (0,1,2), (row, p.stderr[-500:])
        if group=="good": assert p.returncode == 0, row
        else: assert p.returncode != 0, row
    assert row["init_pgo"] == row["mathlib_pgo"], row
    verdicts.append(row)
counts = {str(k):sum(r["init_pgo"]==k for r in verdicts) for k in (0,1,2)}
assert counts == {"0":125,"1":69,"2":2}, counts
(out/"frozen196.json").write_text(json.dumps({"counts":counts,"rows":verdicts},indent=2)+"\n")
print("FLASH_PROFILE_PROTECTED196=" + json.dumps(counts), flush=True)

# Alternate measurement order to reduce one-directional thermal/cache/host-load bias.
measurements = {name: [] for name in bins}
for round_no, order in enumerate((("init_pgo","mathlib_pgo"),("mathlib_pgo","init_pgo"))):
    for name in order:
        binary = bins[name]
        timefile = out / f"{name}_{round_no}.time"
        stdout = out / f"{name}_{round_no}.stdout"
        stderr = out / f"{name}_{round_no}.stderr"
        cmd = ["/usr/bin/time","-f","%U %S %e %M","-o",str(timefile),str(binary),*opts]
        before = time.monotonic()
        with mathlib.open("rb") as src, stdout.open("wb") as dst, stderr.open("wb") as err:
            p = subprocess.run(cmd,stdin=src,stdout=dst,stderr=err,timeout=2400)
        elapsed = time.monotonic()-before
        assert p.returncode == 0, (name, round_no,p.returncode,stderr.read_text(errors="replace")[-2000:])
        cols = timefile.read_text().strip().splitlines()[-1].split()
        assert len(cols) == 4, cols
        user, sys_cpu, _wall, rss = map(float, cols)
        row = {"repetition":round_no,"exit":p.returncode,"cpu_s":user+sys_cpu,
               "wall_s":elapsed,"peak_rss_kb":int(rss),
               "stdout_sha256":hashlib.sha256(stdout.read_bytes()).hexdigest()}
        measurements[name].append(row)
        print("FLASH_PROFILE_MATHLIB="+json.dumps({"arm":name, **row}), flush=True)
assert len(set(row["stdout_sha256"] for rows in measurements.values() for row in rows))==1
summary = {
 name:{
    "cpu_median_s":statistics.median(r["cpu_s"] for r in rows),
    "wall_median_s":statistics.median(r["wall_s"] for r in rows),
    "peak_rss_kb":max(r["peak_rss_kb"] for r in rows)
 } for name,rows in measurements.items()
}
ratio = {
 "candidate_over_baseline_cpu": summary["mathlib_pgo"]["cpu_median_s"]/summary["init_pgo"]["cpu_median_s"],
 "candidate_over_baseline_wall": summary["mathlib_pgo"]["wall_median_s"]/summary["init_pgo"]["wall_median_s"],
 "candidate_over_baseline_rss": summary["mathlib_pgo"]["peak_rss_kb"]/summary["init_pgo"]["peak_rss_kb"]
}
decision = ("CANDIDATE_NEXT_FULL_INSTRUCTION_GATE"
           if ratio["candidate_over_baseline_cpu"] <= 0.98 and
           ratio["candidate_over_baseline_rss"] <= 1.10
           else "REJECT_OR_UNKNOWN_NO_MATERIAL_FULL_MATHLIB_CPU_GAIN")
report = {
 "experiment_sha":os.environ.get("GITHUB_SHA"),
 "upstream":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
 "candidate_semantics":"IDENTICAL source, profile only",
 "source_modifications":"Qualified local sparse prune exact reset + 4x map growth applied identically to both arms",
 "arena":"leanprover/lean-kernel-arena@b83254de5146ef34147ab82a48edbe1856b0edcc",
 "mathlib_sha256":EXPECTED_SHA,"mathlib_bytes":mathlib.stat().st_size,
 "n_jobs":4,"full_mathlib_accept_every_run":True,"protected196":counts,
 "score_instruction_counter":"UNAVAILABLE: cpu and wall proxies, not hardware retired instructions",
 "measurements":measurements,"summary":summary,"ratio":ratio,
 "decision":decision,"promoted":False}
(out/"result.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("FLASH_PROFILE_DECISION="+json.dumps({"decision":decision,"ratio":ratio}),flush=True)
