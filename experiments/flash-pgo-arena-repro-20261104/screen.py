"""A bounded exact-source PGO/no-PGO comparison for the 2026-11-04 Arena magma residual.

Compares the plain checker against the same source with Arena-style profile-guided optimized build. This does not establish correctness on the rest of Arena.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

TARGET_SHA256 = "b8279fa9189a203c6c11b04702c27c0f99a650b37f2b0165dd260b1d14e9ef84"

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for b in iter(lambda: source.read(4 * 1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

def trial(binary, config, fixture, output, arm, tag, seconds):
    stem = output / (arm + "-" + tag)
    so, se, ti = [Path(str(stem) + x) for x in (".stdout", ".stderr", ".time")]
    ret = {"arm": arm, "case": tag, "fixture_sha256": digest(fixture),
           "binary_sha256": digest(binary)}
    start = time.monotonic()
    try:
        with fixture.open("rb") as f, so.open("wb") as stdout, se.open("wb") as stderr:
            p = subprocess.run(["/usr/bin/time", "-f",
                 "wall_s=%e\ncpu_user_s=%U\ncpu_system_s=%S\nrss_kb=%M",
                 "-o", str(ti), str(binary), str(config)],
                stdin=f, stdout=stdout, stderr=stderr, check=False, timeout=seconds)
        ret["rc"] = p.returncode
    except subprocess.TimeoutExpired:
        ret["rc"] = "TIMEOUT"
    ret["elapsed_s"] = round(time.monotonic() - start, 2)
    for k, val in (line.split("=", 1) for line in ti.read_text().splitlines()
                   if "=" in line) if ti.exists() else []:
        ret[k] = float(val)
    ret["stderr_tail"] = se.read_bytes()[-800:].decode(errors="replace") if se.exists() else ""
    return ret

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plain", type=Path, required=True)
    ap.add_argument("--pgo", type=Path, required=True)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--fixtures", type=Path, required=True)
    ap.add_argument("--archive", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    files = {}
    for tag in ("magma-list-pair-n7", "magma-list-pair-n21"):
        matches = list(args.fixtures.rglob(tag + ".ndjson"))
        if len(matches) != 1:
            raise SystemExit("fixture inventory incomplete for " + tag)
        files[tag] = matches[0]
    if digest(files["magma-list-pair-n21"]) != TARGET_SHA256:
        raise SystemExit("magma n21 source SHA drift (stop, do not guess)")
    report = {
        "status": "INCOMPLETE", "plain": digest(args.plain),
        "pgo": digest(args.pgo), "archive_sha256": digest(args.archive),
        "target_sha256": TARGET_SHA256,
        "hypothesis": "Arena-style profile-guided optimization may alter the n21 resource-sensitive verdict",
        "method": "same runner/same source and config, plain release versus Arena-style PGO trained on exact init-prelude; not an Arena CPU replica",
        "runs": [],
    }
    out = args.output / "magma-pgo.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    for index, (arm, tag) in enumerate([
        ("plain", "magma-list-pair-n7"),
        ("pgo", "magma-list-pair-n7"),
        ("pgo", "magma-list-pair-n21"),
        ("plain", "magma-list-pair-n21"),
    ]):
        print("MAGMA_START", json.dumps({"index": index, "arm": arm, "case": tag}), flush=True)
        result = trial(args.plain if arm == "plain" else args.pgo,
                       args.config, files[tag], args.output, arm, tag, 230)
        report["runs"].append(result)
        out.write_text(json.dumps(report, indent=2) + "\n")
        print("MAGMA_RESULT", json.dumps(result), flush=True)
    changed = [r for r in report["runs"] if r["case"] == "magma-list-pair-n21"]
    report["status"] = "OBSERVED_BOUNDED_CAUSAL_SCREEN" if len(changed) == 2 else "INCOMPLETE"
    if len(changed) == 2:
        report["pgo_accepts_n21"] = changed[0]["rc"] == 0
        report["plain_accepts_n21"] = changed[1]["rc"] == 0
    out.write_text(json.dumps(report, indent=2) + "\n")
    print("MAGMA_SUMMARY", json.dumps(report), flush=True)

if __name__ == "__main__":
    main()
