"""Matched native diagnostic on exact official Mathlib bytes; no release gate.

Process statuses are preserved. CPU seconds are never relabeled as Arena virtual
seconds, and an unavailable hardware counter remains unavailable.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import statistics
import subprocess
import time


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--binaries", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--time", type=Path, default=Path("/usr/bin/time"))
    p.add_argument("--rounds", type=int, default=2)
    a = p.parse_args()
    assert a.rounds > 0
    a.out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((Path(__file__).parent / "official-mathlib-input.json").read_text())
    expected = {k: manifest["test"][k] for k in ("size", "sha256")}
    actual = {"size": a.fixture.stat().st_size, "sha256": sha(a.fixture)}
    save(a.out / "input-identity.json", {"actual": actual, "expected": expected,
                                       "authority": manifest["authority"]})
    assert actual == expected, "Mathlib bytes differ from the official input"
    arms = ["baseline", "call_by_need", "full_environment"]
    bins = {arm: (a.binaries / (arm + ".bin")).resolve() for arm in arms}
    save(a.out / "binaries.json", {arm: sha(b) for arm, b in bins.items()})
    config = (a.out / "config.json").resolve()
    save(config, {"use_stdin": True, "num_threads": 1, "nat_extension": True,
                  "string_extension": True, "unsafe_permit_all_axioms": True,
                  "unpermitted_axiom_hard_error": False, "parse_only": False,
                  "print_success_message": True, "print_axioms": False})
    probe = None
    if shutil.which("perf"):
        probe = subprocess.run(["perf", "stat", "-x,", "-e", "instructions:u", "--", "true"],
                               capture_output=True, timeout=15)
    pmu = probe is not None and probe.returncode == 0 and re.search(
        rb"(?m)^\d+,,instructions:u", probe.stderr) is not None
    save(a.out / "pmu-probe.json", {"usable": pmu, "raw_exit": None if probe is None else probe.returncode,
                                   "stderr": "perf unavailable" if probe is None else probe.stderr.decode(errors="replace")})
    rows = []
    for round_no in range(a.rounds):
        order = arms if round_no % 2 == 0 else list(reversed(arms))
        for arm in order:
            tag = f"{arm}-{round_no}"
            timing = a.out / (tag + ".time")
            perf = a.out / (tag + ".perf")
            stdout = a.out / (tag + ".stdout")
            stderr = a.out / (tag + ".stderr")
            cmd = [str(a.time), "-f", "%e\t%U\t%S\t%M", "-o", str(timing)]
            if pmu:
                cmd += ["perf", "stat", "-x,", "-o", str(perf), "-e", "instructions:u", "--"]
            cmd += [str(bins[arm]), str(config)]
            start = time.monotonic()
            with a.fixture.open("rb") as inp, stdout.open("wb") as out, stderr.open("wb") as err:
                proc = subprocess.Popen(cmd, stdin=inp, stdout=out, stderr=err, start_new_session=True)
                try:
                    raw = proc.wait(timeout=4120)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                    raw = "TIMEOUT"
            row = {"arm": arm, "round": round_no, "raw_exit": raw, "expected_exit": 0,
                   "elapsed_s": time.monotonic() - start, "input_sha256": actual["sha256"],
                   "success_message": re.fullmatch(rb"Checked \d+ declarations with no errors\s*", stdout.read_bytes()) is not None,
                   "stderr_tail": stderr.read_bytes()[-1200:].decode(errors="replace")}
            if timing.exists():
                fields = timing.read_text().strip().splitlines()[-1].split("\t")
                if len(fields) == 4:
                    row.update({"wall_s": float(fields[0]), "user_s": float(fields[1]),
                                "system_s": float(fields[2]), "max_rss_kb": int(fields[3])})
                    row["cpu_s"] = row["user_s"] + row["system_s"]
            if perf.exists():
                match = re.search(r"(?m)^(\d+),,instructions:u(?:,|$)", perf.read_text())
                if match:
                    row["instructions_u"] = int(match.group(1))
            rows.append(row)
            save(a.out / "rows.json", rows)
            print(json.dumps(row), flush=True)
    wrong = [r for r in rows if r["raw_exit"] != 0 or not r["success_message"]]
    summary = {"status": "BOUNDED_NATIVE_DIAGNOSTIC" if not wrong else "FAILED_OR_UNAVAILABLE",
               "observations": len(rows), "wrong_or_unavailable": wrong, "hardware_counter_usable": pmu,
               "boundary": "Exact full Mathlib, one worker, matched native build. Not complete Arena qualification or an official ranking."}
    if not wrong:
        for metric in ("cpu_s", "instructions_u"):
            if all(metric in r for r in rows):
                medians = {arm: statistics.median(r[metric] for r in rows if r["arm"] == arm) for arm in arms}
                summary[metric] = {"medians": medians,
                                   "candidate_over_baseline": {arm: medians[arm] / medians["baseline"] for arm in arms[1:]}}
    save(a.out / "summary.json", summary)
    print("SUMMARY", json.dumps(summary), flush=True)
    if wrong:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
