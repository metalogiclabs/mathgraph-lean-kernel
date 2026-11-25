"""Strict process-status oracle for independent Flash architecture trials.

Explicit exclusions remain unknown and are written into every summary. Case
names never reach the checker process. This is not complete release qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", required=True, type=Path)
    p.add_argument("--fixtures", required=True, type=Path)
    p.add_argument("--call-by-need", type=Path)
    p.add_argument("--full-environment", type=Path)
    p.add_argument("--arm", action="append", default=[], help="Named binary as ARM=PATH")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--exclude", action="append", default=[])
    p.add_argument("--threads", type=int, default=1)
    p.add_argument("--official-timeouts", action="store_true")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(a.results.read_text())
    cases = {t["name"]: t for t in manifest["tests"] if t.get("outcome") in ("accept", "reject")
             and t.get("size", 0) <= 10 * 1024 * 1024}
    assert len(cases) == 230
    assert set(a.exclude) <= cases.keys()
    bins = {name: path.resolve() for name, path in
            [("call_by_need", a.call_by_need), ("full_environment", a.full_environment)] if path is not None}
    for item in a.arm:
        name, path = item.split("=", 1)
        assert name and name not in bins
        bins[name] = Path(path).resolve()
    assert bins
    config = (a.out / "config.json").resolve()
    assert a.threads > 0
    save(config, {"use_stdin": True, "num_threads": a.threads, "nat_extension": True,
                  "string_extension": True, "unsafe_permit_all_axioms": True,
                  "unpermitted_axiom_hard_error": False, "parse_only": False,
                  "print_axioms": False})
    save(a.out / "identity.json", {"source": manifest["meta"], "binaries": {k: digest(v) for k, v in bins.items()},
                                   "excluded_unknown": sorted(a.exclude), "attempted_per_arm": len(cases) - len(set(a.exclude)),
                                   "threads": a.threads, "official_timeouts": a.official_timeouts})
    rows = []
    for name, meta in sorted(cases.items()):
        if name in a.exclude:
            continue
        fixture = a.fixtures / (name + ".ndjson")
        assert fixture.stat().st_size == meta["size"] and digest(fixture) == meta["sha256"], name
        expected = 0 if meta["outcome"] == "accept" else 1
        for arm, binary in bins.items():
            start = time.monotonic()
            with fixture.open("rb") as inp:
                try:
                    r = subprocess.run([str(binary), str(config)], stdin=inp, capture_output=True,
                                       timeout=meta.get("timeout") if a.official_timeouts else 180)
                    raw, stdout, stderr = r.returncode, r.stdout, r.stderr
                except subprocess.TimeoutExpired as e:
                    raw, stdout, stderr = "TIMEOUT", e.stdout or b"", e.stderr or b""
            row = {"name": name, "arm": arm, "expected_exit": expected, "raw_exit": raw,
                   "input_sha256": meta["sha256"], "elapsed_s": round(time.monotonic() - start, 4),
                   "stderr_tail": stderr[-300:].decode(errors="replace"),
                   "stdout_sha256": hashlib.sha256(stdout).hexdigest(), "stderr_sha256": hashlib.sha256(stderr).hexdigest()}
            rows.append(row)
            save(a.out / "rows.json", rows)
            if raw != expected:
                print("WRONG_OR_UNAVAILABLE", json.dumps(row), flush=True)
        if len(rows) % 40 == 0:
            print("OBSERVATIONS", len(rows), flush=True)
    summary = {arm: {"attempted": sum(r["arm"] == arm for r in rows),
                     "correct": sum(r["arm"] == arm and r["raw_exit"] == r["expected_exit"] for r in rows),
                     "wrong_or_unavailable": [r for r in rows if r["arm"] == arm and r["raw_exit"] != r["expected_exit"]],
                     "excluded_unknown": sorted(a.exclude)} for arm in bins}
    summary["boundary"] = "Raw status on attempted portable inputs. Explicit exclusions remain unknown. No ten-large-input qualification."
    save(a.out / "summary.json", summary)
    print("SUMMARY", json.dumps(summary), flush=True)
    if any(summary[arm]["wrong_or_unavailable"] for arm in bins):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
