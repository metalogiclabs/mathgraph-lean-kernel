"""Exact-input, raw-verdict comparison for the independent Flash cache experiment.

Inputs are the Arena results.json and its extracted portable fixture tree. This
harness never supplies test names to a checker and never rewrites exit codes.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time

SAMPLES = ["init-prelude", "perf/grind-ring-5", "perf/magma-list-deep-n21",
           "perf/magma-list-pair-n7", "perf/fueled-chain"]


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=["portable", "samples"])
    p.add_argument("--results", required=True, type=Path)
    p.add_argument("--fixtures", required=True, type=Path)
    p.add_argument("--baseline", required=True, type=Path)
    p.add_argument("--candidate", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--valgrind", default="valgrind")
    p.add_argument("--rounds", type=int, default=1)
    p.add_argument("--case-timeout", type=int, help="Explicit per-process time limit; default is unchanged")
    a = p.parse_args()
    assert a.rounds > 0
    assert a.case_timeout is None or a.case_timeout > 0
    a.out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(a.results.read_text())
    tests = {t["name"]: t for t in manifest["tests"]}
    binaries = {"baseline": a.baseline.resolve(), "candidate": a.candidate.resolve()}
    hashes = {arm: digest(binary) for arm, binary in binaries.items()}
    config = a.out / "config.json"
    save(config, {"use_stdin": True, "num_threads": 1, "nat_extension": True,
                  "string_extension": True, "unsafe_permit_all_axioms": True,
                  "unpermitted_axiom_hard_error": False})
    names = SAMPLES if a.mode == "samples" else sorted(
        name for name, t in tests.items() if t.get("outcome") in ("accept", "reject")
        and t.get("size", 0) <= 10 * 1024 * 1024)
    if a.mode == "portable":
        assert len(names) == 230
    save(a.out / "identity.json", {"arena": manifest["meta"], "binaries": hashes,
                                   "mode": a.mode, "names": names})
    rows = []
    for name in names:
        meta = tests[name]
        fixture = a.fixtures / (name + ".ndjson")
        assert fixture.stat().st_size == meta["size"] and digest(fixture) == meta["sha256"], name
        expected = 0 if meta["outcome"] == "accept" else 1
        for round_no in range(a.rounds):
            order = ["baseline", "candidate"] if round_no % 2 == 0 else ["candidate", "baseline"]
            for arm in order:
                tag = f"{name.replace('/', '_')}-{round_no}-{arm}"
                cmd = [str(binaries[arm]), str(config.resolve())]
                profile = a.out / (tag + ".callgrind")
                if a.mode == "samples":
                    cmd = [a.valgrind, "--tool=callgrind", "--callgrind-out-file=" + str(profile)] + cmd
                start = time.monotonic()
                with fixture.open("rb") as inp, (a.out / (tag + ".stdout")).open("wb") as stdout, \
                        (a.out / (tag + ".stderr")).open("wb") as stderr:
                    try:
                        completed = subprocess.run(cmd, stdin=inp, stdout=stdout, stderr=stderr,
                                                   timeout=a.case_timeout or (600 if a.mode == "samples" else 180))
                        status = completed.returncode
                    except subprocess.TimeoutExpired:
                        status = "TIMEOUT"
                row = {"name": name, "arm": arm, "round": round_no, "raw_exit": status,
                       "expected": expected, "input_sha256": meta["sha256"],
                       "elapsed_s": round(time.monotonic() - start, 4)}
                if a.mode == "samples" and profile.exists():
                    match = re.findall(r"^summary:\s*(\d+)", profile.read_text(), re.M)
                    row["guest_Ir"] = int(match[-1]) if match else None
                rows.append(row)
                save(a.out / "rows.json", rows)
                print(json.dumps(row), flush=True)
    wrong = [r for r in rows if r["raw_exit"] != r["expected"]]
    summary = {"observations": len(rows), "wrong_or_unavailable": wrong,
               "boundary": "Raw process status; software guest instructions are not an official Arena score."}
    if a.mode == "samples" and not wrong:
        totals = {(name, arm): sum(r["guest_Ir"] for r in rows if r["name"] == name and r["arm"] == arm)
                  for name in names for arm in binaries}
        ratios = {name: totals[name, "candidate"] / totals[name, "baseline"] for name in names}
        geomean = math.exp(sum(math.log(r) for r in ratios.values()) / len(ratios))
        summary.update({"ratios": ratios, "geomean_ratio": geomean,
                        "passes_1_percent_gate": geomean <= 0.99})
    save(a.out / "summary.json", summary)
    print("SUMMARY", json.dumps(summary), flush=True)
    if wrong:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
