"""Qualify the frozen inline candidate and compare target-cpu=native builds.

The nine large replays extend the exact a76e2b executable's generic qualification.
The native test changes the compiler target and therefore retains its own binary
identities, portable qualification, and full-input observations. It makes no
hardware-instruction, Arena-rank, or release claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import statistics
import subprocess
import time
import zipfile

BASE = "bc704eebed4e009bc66af1a849f18315c11f1926"
SOURCE = "de6696fcecbe99e6fcab5bb68c5974e1e9a04e49"
ARCHIVE = "6f55b2f7d754e4310589fe74aed040ae98ba82d39ba395bffd7cb6d439a0821e"
GENERIC = "a76e2bbfe07ce80b204937548b7a00524bee1bff113fe19c9e1244ed93443f46"
EXPECTED = {"cedar":151772,"con-leche":38246,"cslib":413186,"init":59979,"perf/magma-string-n4":3542,"perf/magma-string-pair-n9":3542,"reachability":4846,"std":103885,"navier-stokes-euler":129845}
FLAGS = ["--stdin", "--threads", "2", "--nat-extension", "--string-extension", "--axiom-allow-all"]

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")

def execute(binary, fixture, out, tag, budget):
    resources = out / (tag + ".time")
    command = ["/usr/bin/time", "-f", "%e\t%U\t%S\t%M", "-o", str(resources), str(binary)] + FLAGS
    start = time.monotonic()
    with fixture.open("rb") as inp, (out / (tag + ".stdout")).open("wb") as stdout, (out / (tag + ".stderr")).open("wb") as stderr:
        proc = subprocess.Popen(command, stdin=inp, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            code = proc.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            code = "UNKNOWN_TIME_BUDGET"
    counts = re.findall(rb"[Cc]hecked (\d+) declarations", (out / (tag + ".stdout")).read_bytes())
    row = {"raw_exit": code, "checked_declarations": int(counts[-1]) if counts else None,
           "elapsed_s": time.monotonic() - start}
    if resources.exists():
        fields = resources.read_text().splitlines()[-1].split("\t")
        if len(fields) == 4:
            row.update(wall_s=float(fields[0]), cpu_s=float(fields[1]) + float(fields[2]), max_rss_kib=int(fields[3]))
    return row

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("mode", choices=["thaw", "large", "native"])
p.add_argument("--out", type=Path, required=True)
p.add_argument("--archive", type=Path)
p.add_argument("--fixture", type=Path)
p.add_argument("--candidate", type=Path)
p.add_argument("--baseline", type=Path)
p.add_argument("--case")
a = p.parse_args()
a.out = a.out.resolve()
a.out.mkdir(parents=True, exist_ok=True)

if a.mode == "thaw":
    assert digest(a.archive) == ARCHIVE
    with zipfile.ZipFile(a.archive) as z:
        assert z.testzip() is None
        data = z.read("builds/candidate.bin")
        assert hashlib.sha256(data).hexdigest() == GENERIC
        binary = a.out / "candidate.bin"
        binary.write_bytes(data)
        binary.chmod(0o555)
    save(a.out / "frozen-identity.json", {"archive_sha256": ARCHIVE, "binary_sha256": GENERIC,
         "artifact_id": 15073369717, "run_id": 45723515088, "base_commit": BASE, "candidate_source_tree": SOURCE})
elif a.mode == "large":
    assert digest(a.candidate) == GENERIC
    manifest = json.loads(Path("experiments/flash-upstream-repair-20261126/official-inputs.json").read_text())
    matches = [t for t in manifest["tests"] if t["name"] == a.case]
    assert len(matches) == 1 and a.case in EXPECTED
    meta = matches[0]
    identity = {"name": a.case, "size": a.fixture.stat().st_size, "sha256": digest(a.fixture)}
    save(a.out / "input.json", identity)
    assert meta["outcome"] == "accept" and identity["size"] == meta["size"] and identity["sha256"] == meta["sha256"]
    row = execute(a.candidate.resolve(), a.fixture, a.out, "candidate", meta["timeout"])
    row.update(name=a.case, input_sha256=identity["sha256"], binary_sha256=GENERIC,
               expected_declarations=EXPECTED[a.case], threads=2,
               boundary="Exact frozen generic candidate, unchanged complete prescribed bytes and original timeout.")
    save(a.out / "verdict.json", row)
    print("LARGE_VERDICT", json.dumps(row), flush=True)
    assert row["raw_exit"] == 0 and row["checked_declarations"] == EXPECTED[a.case], row
    assert digest(a.candidate) == GENERIC
else:
    identity = {"size": a.fixture.stat().st_size, "sha256": digest(a.fixture)}
    assert identity == {"size": 6326141213, "sha256": "f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec"}
    binaries = {"baseline": a.baseline.resolve(), "candidate": a.candidate.resolve()}
    hashes = {name: digest(binary) for name, binary in binaries.items()}
    gate = "Three alternating pairs; candidate median CPU <=0.99 baseline, each paired CPU ratio <1, maximum RSS <=1.05 baseline. Every run must exit 0 after exactly 739167 declarations."
    save(a.out / "identity.json", {"input": identity, "binary_sha256": hashes, "base_commit": BASE,
         "candidate_source_tree": SOURCE, "build_flags": "-C target-cpu=native", "threads": 2,
         "gate": gate, "hardware_instructions": None,
         "boundary": "Matched native CPU/RSS diagnostic only. Hardware event unavailable in prior capability probe; no Arena score or release promotion."})
    rows = []
    for pair, order in enumerate((("baseline", "candidate"), ("candidate", "baseline"), ("baseline", "candidate"))):
        for arm in order:
            assert {n: digest(b) for n, b in binaries.items()} == hashes
            row = execute(binaries[arm], a.fixture, a.out, f"{arm}-{pair}", 600)
            row.update(arm=arm, pair=pair)
            rows.append(row)
            save(a.out / "rows.json", rows)
            print(json.dumps(row), flush=True)
            assert row["raw_exit"] == 0 and row["checked_declarations"] == 739167 and "cpu_s" in row, row
    assert {n: digest(b) for n, b in binaries.items()} == hashes
    medians = {arm: {key: statistics.median(r[key] for r in rows if r["arm"] == arm)
                   for key in ("cpu_s", "wall_s", "max_rss_kib")} for arm in binaries}
    by_pair = {(r["pair"], r["arm"]): r for r in rows}
    paired = [by_pair[n, "candidate"]["cpu_s"] / by_pair[n, "baseline"]["cpu_s"] for n in range(3)]
    cpu_ratio = medians["candidate"]["cpu_s"] / medians["baseline"]["cpu_s"]
    peaks = {arm: max(r["max_rss_kib"] for r in rows if r["arm"] == arm) for arm in binaries}
    rss_ratio = peaks["candidate"] / peaks["baseline"]
    supported = hashes["baseline"] != hashes["candidate"] and cpu_ratio <= 0.99 and all(r < 1 for r in paired) and rss_ratio <= 1.05
    summary = {"state": "WARRANTED_BOUNDED_NATIVE_CPU_GAIN" if supported else "NO_NATIVE_CPU_PROMOTION",
               "observations": len(rows), "medians": medians, "cpu_ratio": cpu_ratio,
               "paired_cpu_ratios": paired, "peak_rss_kib": peaks, "peak_rss_ratio": rss_ratio,
               "gate": gate, "gate_passed": supported, "hardware_instructions": None,
               "boundary": "Native build, full original Mathlib only. This does not qualify the native build's nine other large inputs, confer a hardware score, or change PR398."}
    save(a.out / "summary.json", summary)
    print("NATIVE_SUMMARY", json.dumps(summary), flush=True)
