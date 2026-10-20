#!/usr/bin/env python3
"""Paired whole-process guest-instruction test of *identical* Flash checker source.

Both builds use the same Rust source, release profile, x86-64 ISA, and 4 checking
threads. Only the PGO training workload differs (Init.Prelude vs full Mathlib).
Callgrind guest Ir is not the Arena PMU hardware retired-instruction metric.
"""
import hashlib
import json
import math
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

root, mathlib, output = map(pathlib.Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
BINS = {"init_pgo": pathlib.Path("/tmp/flash-profile-init"),
        "mathlib_pgo": pathlib.Path("/tmp/flash-profile-mathlib")}
OPTIONS = ["--stdin", "--nat-extension", "--string-extension",
           "--axiom-allow-all", "--threads", "4"]
HASH = "22c5de83469408950005589a3bc5ef5157c65549b5a802f85d567c29151306a6"
assert mathlib.stat().st_size == 6184415052
with mathlib.open("rb") as f:
    digest = hashlib.file_digest(f, "sha256").hexdigest()
assert digest == HASH, (digest, HASH)
for name, path in BINS.items():
    assert path.is_file(), (name, path)
    print("FLASH_GUEST_BINARY=" + json.dumps({"name":name,
          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}), flush=True)

cases = [(kind, p) for kind in ("good", "bad")
         for p in sorted((root / kind).rglob("*.ndjson"))]
assert sum(k == "good" for k, _ in cases) == 125
assert sum(k == "bad" for k, _ in cases) == 71
verdicts = []
for group, file in cases:
    row = {"case":str(file.relative_to(root)), "group":group,
           "sha256":hashlib.sha256(file.read_bytes()).hexdigest()}
    for name, binary in BINS.items():
        with file.open("rb") as inp:
            proc = subprocess.run([str(binary), *OPTIONS], stdin=inp,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
        row[name] = proc.returncode
        assert proc.returncode in (0, 1, 2), (row, proc.stderr[-400:])
        assert (proc.returncode == 0) if group == "good" else (proc.returncode != 0), row
    assert row["init_pgo"] == row["mathlib_pgo"], row
    verdicts.append(row)
counts = {str(i): sum(r["init_pgo"] == i for r in verdicts) for i in (0,1,2)}
assert counts == {"0":125, "1":69, "2":2}, counts
(output / "protected196.json").write_text(json.dumps({"counts":counts,"rows":verdicts},indent=2)+"\n")
print("FLASH_GUEST_PROTECTED=" + json.dumps(counts), flush=True)

focus = ("init-prelude","perf/grind-ring-5","perf/magma-list-pair-n7",
         "perf/magma-list-deep-n21","perf/fueled-chain")
observations = []
for idx, test in enumerate(focus):
    file = root / "good" / (test + ".ndjson")
    assert file.is_file()
    samples = {}
    # Alternate arms to avoid systematic first-process bias.
    names = list(BINS) if idx % 2 == 0 else list(reversed(BINS))
    for name in names:
        callgrind = output / (test.replace("/","_") + "-" + name + ".callgrind")
        cmd = ["valgrind","--tool=callgrind","--quiet","--collect-jumps=no",
               "--callgrind-out-file=" + str(callgrind), str(BINS[name]), *OPTIONS]
        with file.open("rb") as inp:
            p = subprocess.run(cmd, stdin=inp, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE, timeout=1000)
        assert p.returncode == 0, (name, test, p.returncode, p.stderr[-800:])
        total = next((int(line.split()[1]) for line in callgrind.read_text().splitlines()
                    if line.startswith("summary: ")), None)
        assert total is not None and total > 1000000, (name, test, total)
        samples[name] = total
        callgrind.unlink()
    row = {"test":test,"init_Ir":samples["init_pgo"],
           "mathlib_Ir":samples["mathlib_pgo"],
           "ratio":samples["mathlib_pgo"]/samples["init_pgo"]}
    observations.append(row)
    print("FLASH_GUEST_IR=" + json.dumps(row), flush=True)

geo = math.exp(sum(math.log(x["ratio"]) for x in observations) / len(observations))
largest = max(x["ratio"] for x in observations)
decision = ("ELIGIBLE_FOR_FULL_MATHLIB_INSTRUCTION_AB"
            if geo <= 0.995 and largest <= 1.01
            else "NO_MATERIAL_FIVE_CASE_INSTRUCTION_WIN")
result = {
    "run_sha":os.environ.get("GITHUB_SHA"),
    "timestamp":datetime.now(timezone.utc).isoformat(),
    "source_ref":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
    "common_modifications":"same qualified sparse pruning + 4x map growth in both arms",
    "sole_tested_difference":"compiler profile trained on whole Mathlib vs Init.Prelude",
    "input_sha256":HASH, "protected196":counts,
    "counter":"Valgrind Callgrind whole-process guest Ir, not Arena PMU instructions",
    "geometric_ratio":geo, "largest_case_ratio":largest, "observations":observations,
    "decision":decision, "official_rank_qualified":False,
}
(output / "instruction-decision.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
print("FLASH_GUEST_DECISION="+json.dumps({"decision":decision,
    "geometric_ratio":geo,"largest_case_ratio":largest}),flush=True)
