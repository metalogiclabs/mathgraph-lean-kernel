#!/usr/bin/env python3
"""Evidence-only Mathlib A/B tournament. Never infer Arena rank from wall-time."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

export = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
assert export.is_file() and export.stat().st_size > 3_000_000_000, export
flash2 = "/tmp/flash-msi-config2.json"
flash4 = "/tmp/flash-msi-config4.json"
commands = {
    "mathgraph_published_2t": ["/tmp/msi-before.bin", flash2],
    "mathgraph_candidate_2t": ["/tmp/msi-after.bin", flash2],
    "mathgraph_candidate_4t": ["/tmp/msi-after.bin", flash4],
    "sokonanoda_official_4t": [
        "/tmp/msi-leader.bin", "--stdin", "--nat-extension",
        "--string-extension", "--axiom-allow-all", "--threads", "4",
    ],
}
runs = {name: [] for name in commands}
for rep in range(2):
    order = list(commands) if rep == 0 else list(reversed(commands))
    for name in order:
        meter = out / ("time-" + name + "-" + str(rep) + ".txt")
        stderr = out / ("stderr-" + name + "-" + str(rep) + ".txt")
        with export.open("rb") as fin, stderr.open("wb") as err:
            start = time.monotonic()
            proc = subprocess.run(
                ["/usr/bin/time", "-f", "%U %S %e %M", "-o", str(meter),
                 *commands[name]], stdin=fin, stdout=subprocess.DEVNULL,
                stderr=err, timeout=2700)
            wall = time.monotonic() - start
        timing = meter.read_text().strip().splitlines()[-1].split()
        assert len(timing) == 4, (name, timing)
        user, system, reported_wall, rss = map(float, timing)
        data = {"run": rep, "exit": proc.returncode,
                "cpu_seconds": user + system, "wall_seconds": wall,
                "reported_wall_seconds": reported_wall, "max_rss_kb": int(rss)}
        runs[name].append(data)
        print("MSI_MATHLIB_RUN=" + json.dumps({"checker": name, **data}), flush=True)
        if proc.returncode != 0:
            raise RuntimeError("Valid Mathlib export not accepted: " + name)
summary = {name: {
    "median_cpu_seconds": statistics.median(x["cpu_seconds"] for x in values),
    "median_wall_seconds": statistics.median(x["wall_seconds"] for x in values),
    "peak_rss_kb": max(x["max_rss_kb"] for x in values),
} for name, values in runs.items()}
score = {
    "source_candidate": os.environ["GITHUB_SHA"],
    "source_baseline": os.environ["MSI_BASE_SHA"],
    "leader_revision": "7645b1e1fcacfe410c99141f1234381d995b325d",
    "arena_revision": "b83254de5146ef34147ab82a48edbe1856b0edcc",
    "export_bytes": export.stat().st_size,
    "metric": "same-run Linux wall and CPU; not Arena retired instructions",
    "runs": runs,
    "summary": summary,
    "official_rank_proven": False,
}
(out / "mathlib.json").write_text(json.dumps(score, indent=2, sort_keys=True) + "\n")
print("MSI_MATHLIB_SUMMARY=" + json.dumps(summary), flush=True)

# A native PMU measurement is indispensable for claiming official score improvement.
# GitHub-hosted runners have historically blocked this event. Report the limitation,
# rather than substituting a fabricated instruction count.
perf = shutil.which("perf")
if not perf:
    print("MSI_ARENA_INSTRUCTIONS=UNAVAILABLE:no-perf", flush=True)
    sys.exit(0)
probe = subprocess.run([perf, "stat", "-e", "instructions", "--", "true"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=15)
if probe.returncode != 0:
    print("MSI_ARENA_INSTRUCTIONS=UNAVAILABLE:pmu-permissions-or-hardware",
          flush=True)
    sys.exit(0)
counter = {}
for name in commands:
    target = out / ("perf-" + name + ".txt")
    with export.open("rb") as fin:
        p = subprocess.run([perf, "stat", "-x", ";", "-e", "instructions",
                            "-o", str(target), "--", *commands[name]],
                           stdin=fin, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, timeout=2700)
    if p.returncode != 0:
        print("MSI_ARENA_INSTRUCTIONS=UNAVAILABLE:failed-run", flush=True)
        sys.exit(0)
    number = None
    for line in target.read_text().splitlines():
        parts = line.split(";")
        if len(parts) >= 3 and parts[2].strip() == "instructions":
            raw = parts[0].replace(",", "").strip()
            if raw.isdigit():
                number = int(raw)
    if number is None:
        print("MSI_ARENA_INSTRUCTIONS=UNAVAILABLE:missing-counter", flush=True)
        sys.exit(0)
    counter[name] = number
score["hardware_instruction_counts"] = counter
score["official_rank_proven"] = False  # full-suite scoring remains separate
(out / "mathlib.json").write_text(json.dumps(score, indent=2, sort_keys=True) + "\n")
print("MSI_MATHLIB_INSTRUCTIONS=" + json.dumps(counter), flush=True)
