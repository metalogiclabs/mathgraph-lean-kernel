#!/usr/bin/env python3
"""Two-arm protected test of Soko's PtrMap shrink hysteresis.

Both arms use identical pinned upstream source and verified sparse+4x
parent patches; candidate changes *only* shrink hysteresis. Callgrind guest
Ir is a developmental proxy, never Arena retired instructions.
"""
import hashlib, json, math, os, pathlib, re, subprocess, sys
root = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
bins = {
    "baseline": "/tmp/soko-hysteresis-baseline.bin",
    "candidate": "/tmp/soko-hysteresis-candidate.bin",
}
args = ["--stdin", "--nat-extension", "--string-extension",
        "--axiom-allow-all", "--threads", "1"]
good = sorted((root / "good").rglob("*.ndjson"))
bad = sorted((root / "bad").rglob("*.ndjson"))
assert len(good) == 125 and len(bad) == 71, (len(good), len(bad))
verdicts = []
for expected, cases in (("good", good), ("bad", bad)):
    for p in cases:
        outcome = {}
        for arm, binary in bins.items():
            with p.open("rb") as inp:
                result = subprocess.run([binary, *args], stdin=inp,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
            outcome[arm] = result.returncode
        assert outcome["baseline"] == outcome["candidate"], (str(p), outcome)
        rc = outcome["candidate"]
        assert (rc == 0 if expected == "good" else rc in (1, 2)), (str(p), outcome)
        verdicts.append({"file": str(p.relative_to(root)), "rc": rc})
counts = {"accepted": sum(v["rc"] == 0 for v in verdicts),
          "rejected": sum(v["rc"] == 1 for v in verdicts),
          "declined": sum(v["rc"] == 2 for v in verdicts)}
assert counts == {"accepted": 125, "rejected": 69, "declined": 2}, counts
print("HYSTERESIS_VERDICTS=" + json.dumps({"count": len(verdicts),
    **counts, "identical": True, "wrong": 0}), flush=True)

rows = []
for case in ["init-prelude", "perf/grind-ring-5",
             "perf/magma-list-deep-n21", "perf/magma-list-pair-n7",
             "perf/fueled-chain"]:
    path = root / "good" / (case + ".ndjson")
    assert path.is_file(), path
    row = {"case": case, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    for arm, binary in bins.items():
        rss_path = out / ("rss-" + case.replace("/", "_") + "-" + arm + ".txt")
        with path.open("rb") as fin:
            measured = subprocess.run(["/usr/bin/time", "-f", "%M",
                "-o", str(rss_path), binary, *args], stdin=fin,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=420)
        assert measured.returncode == 0, (case, arm, "native", measured.returncode)
        row[arm + "_rss_kb"] = int(rss_path.read_text().strip())
        rss_path.unlink()
        profile = out / (case.replace("/", "_") + "-" + arm + ".callgrind")
        cmd = ["valgrind", "--tool=callgrind", "--cache-sim=no",
               "--branch-sim=no", "--callgrind-out-file=" + str(profile),
               binary, *args]
        with path.open("rb") as fin:
            measured = subprocess.run(cmd, stdin=fin,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=650)
        assert measured.returncode == 0, (case, arm, "callgrind", measured.returncode,
                                           measured.stderr[-800:])
        m = re.search(r"^summary:\s*(\d+)\s*$", profile.read_text(), re.M)
        assert m, (case, arm, "no Callgrind Ir")
        row[arm + "_guest_Ir"] = int(m.group(1))
        profile.unlink()
    row["candidate_over_baseline_ir"] = row["candidate_guest_Ir"] / row["baseline_guest_Ir"]
    row["candidate_over_baseline_rss"] = (
        row["candidate_rss_kb"] / max(1, row["baseline_rss_kb"]))
    print("HYSTERESIS_CASE=" + json.dumps(row), flush=True)
    rows.append(row)
ratio = math.exp(sum(math.log(r["candidate_over_baseline_ir"]) for r in rows) / len(rows))
max_rss = max(r["candidate_over_baseline_rss"] for r in rows)
decision = ("CANDIDATE_FOR_OFFICIAL_STDIN_MATHLIB" if ratio <= 0.99 and max_rss <= 1.10
            else "REJECTED_OR_UNRESOLVED_ON_FIVE_CASE_PROXY")
report = {
    "source": "intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
    "repository_experiment": os.environ.get("GITHUB_SHA"),
    "common_ancestor": "sparse touched-slot + exact 4x PtrMap growth",
    "intervention": "PtrMap reset_shrink threshold 4x -> 16x",
    "metric": "full-process Valgrind Callgrind guest Ir, NOT Arena PMU",
    "arbitrary_cpu_time_not_used_as_instruction_proxy": True,
    "portable196": verdicts, "verdict_counts": counts,
    "selected_cases": rows, "geomean_candidate_over_baseline_ir": ratio,
    "max_candidate_over_baseline_rss": max_rss,
    "official_rank_qualified": False, "decision": decision
}
(out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print("HYSTERESIS_SUMMARY=" + json.dumps({
    "guest_ir_ratio": ratio, "max_rss_ratio": max_rss, "decision": decision,
    "official_rank_qualified": False}), flush=True)
