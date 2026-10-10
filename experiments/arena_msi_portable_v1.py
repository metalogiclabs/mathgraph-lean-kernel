#!/usr/bin/env python3
"""Frozen Arena verdict parity and small-case performance tournament.
All clock measurements are explicitly NOT retired-instruction score measurements.
"""
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

root = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
baseline = "/tmp/flash-msi-baseline"
candidate = "/tmp/flash-msi-candidate"
modes = {
    "baseline2": (baseline, "/tmp/flash-msi-config2.json"),
    "candidate2": (candidate, "/tmp/flash-msi-config2.json"),
    "candidate4": (candidate, "/tmp/flash-msi-config4.json"),
}
good = sorted((root / "good").rglob("*.ndjson"))
bad = sorted((root / "bad").rglob("*.ndjson"))
assert len(good) >= 125 and len(bad) >= 71, (len(good), len(bad))
cases = [(True, p) for p in good] + [(False, p) for p in bad]
rows = []
for expected, path in cases:
    outcomes = {}
    with path.open("rb") as f:
        data = f.read()
    for mode, (binary, config) in modes.items():
        result = subprocess.run([binary, config], input=data, timeout=90,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        outcomes[mode] = {
            "rc": result.returncode,
            "stdout_digest": hashlib.sha256(result.stdout).hexdigest(),
            "stderr_tail": result.stderr.decode(errors="replace").splitlines()[-1:],
        }
    assert len({v["rc"] for v in outcomes.values()}) == 1, (str(path), outcomes)
    if expected:
        assert outcomes["candidate4"]["rc"] == 0, str(path)
    else:
        assert outcomes["candidate4"]["rc"] != 0, str(path)
    rows.append({"case": str(path.relative_to(root)), "valid": expected, "results": outcomes})
print("MSI_PORTABLE_VERDICTS=" + json.dumps({
    "valid": len(good), "invalid": len(bad), "differences": 0,
    "bad_accepts": 0, "good_rejects": 0
}), flush=True)
(out / "verdicts.json").write_text(json.dumps(rows, indent=2) + "\n")
focus = ["init-prelude", "perf/grind-ring-5", "perf/magma-list-pair-n7",
         "perf/magma-list-deep-n21", "perf/fueled-chain"]
measure = []
for case in focus:
    path = root / "good" / (case + ".ndjson")
    if not path.exists():
        continue
    results = {mode: [] for mode in modes}
    for repetition in range(3):
        order = list(modes) if repetition % 2 == 0 else list(reversed(modes))
        for mode in order:
            binary, config = modes[mode]
            meter = out / ("time-" + case.replace("/", "_") + "-" + mode + "-" + str(repetition))
            with path.open("rb") as file:
                start = time.monotonic()
                result = subprocess.run(
                    ["/usr/bin/time", "-f", "%U %S %e %M", "-o", str(meter),
                     binary, config], stdin=file,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
                wall = time.monotonic() - start
            values = meter.read_text().strip().splitlines()[-1].split()
            if len(values) != 4:
                raise RuntimeError((meter, values))
            user, system, elapsed, rss = map(float, values)
            assert result.returncode == 0, (case, mode, result.stderr[-1200:])
            results[mode].append({"cpu": user + system, "wall": wall, "rss_kb": int(rss)})
    medians = {key: {
        "cpu": statistics.median(x["cpu"] for x in values),
        "wall": statistics.median(x["wall"] for x in values),
        "rss_kb": statistics.median(x["rss_kb"] for x in values),
    } for key, values in results.items()}
    measure.append({"case": case, "median": medians, "runs": results})
    print("MSI_PORTABLE_AB=" + json.dumps({"case": case, "median": medians}), flush=True)
(out / "portfolio.json").write_text(json.dumps({
    "baseline": os.environ["MSI_BASE_SHA"],
    "candidate": os.environ["GITHUB_SHA"],
    "authority": "portable frozen Arena corpus, Linux CPU and wall, NOT retired instructions",
    "cases": measure,
}, indent=2) + "\n")
