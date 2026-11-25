"""Source-pinned Arena recovery diagnostic; no test-specific kernel dispatch.

Three exact checker arms, official source bytes and expected labels. A historical
Mathlib pass or a passing diagnostic job is not current release qualification.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time
import zipfile

ARENA = "leanprover/lean-kernel-arena"
ARENA_REV = "99195b6b009bc3df2c946ddbcfa4a2ab1eb40350"
RUN = 45225857402
PUBLISHED = "78c7502bac8a5ba000057b3f083bc0595ac65750"
STACK = "6c2889330be236b3bc063b3415de6e9af65ecfe1"
SOKO = "9a021b66f804a1d1df68a981337c67413ef72f6b"
ARTIFACTS = {
    "results": (14850076619, "5df29b59d35934fe0276e85c06413fc4ae55100818cbb096239d8cf4b1cee7fb"),
    "stats": (14845265574, "d339db95cf6ca74ed0e928fe4923cd90fae161c4aeeee52f45b64af4ec91ddd0"),
    "tarball": (14842971830, "4d33cfdd5754e9ebc06b546a3cc4ae41c8e3d0a1624b48ad4ba2ac6aeafb76ec"),
}
SIX = {"bugs/closure-level-subst", "bugs/pi-closure-context",
       "bugs/nested-rec-rule-nfields", "bugs/nested-name-capture",
       "bugs/unit-rec-rule", "other/inductive-undeclared-universe"}

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

def download(out, kind):
    aid, expected = ARTIFACTS[kind]
    p = out / (kind + ".zip")
    with p.open("wb") as f:
        subprocess.run(["gh", "api", f"repos/{ARENA}/actions/artifacts/{aid}/zip"],
                       stdout=f, check=True)
    assert sha(p) == expected, (kind, sha(p), expected)
    return p

def source_manifest(out):
    run = json.loads(subprocess.check_output(
        ["gh", "api", f"repos/{ARENA}/actions/runs/{RUN}"]))
    assert run["head_sha"] == ARENA_REV, run["head_sha"]
    dump(out / "arena-source-run.json", {k: run.get(k) for k in
         ("id", "head_sha", "html_url", "status", "conclusion", "updated_at")})
    z = download(out, "results")
    with zipfile.ZipFile(z) as archive:
        candidates = []
        for n in archive.namelist():
            if not n.endswith(".json"):
                continue
            obj = json.loads(archive.read(n))
            if isinstance(obj, dict) and isinstance(obj.get("tests"), list):
                candidates.append(obj)
    assert len(candidates) == 1, "No unique official results manifest"
    data = candidates[0]
    assert data["meta"]["git_revision"] == ARENA_REV
    assert len({x["name"] for x in data["tests"]}) == len(data["tests"])
    tests = {x["name"]: x for x in data["tests"]}
    assert "mathlib" in tests and tests["mathlib"]["outcome"] == "accept"
    for name in ("mathgraph", "sokonanoda", "nano-lean"):
        rows = [x for x in data["checkers"] if x["name"] == name]
        assert len(rows) == 1, name
        assert rows[0]["rev"] == {"mathgraph": PUBLISHED,
            "sokonanoda": SOKO,
            "nano-lean": "5cd4a25de7cdd8a5fadde3fec53e41a6a8693138"}[name]
    dump(out / "official-results.json", data)
    return tests

def unpack_portable(out, tests):
    p = download(out, "tarball")
    with zipfile.ZipFile(p) as z:
        members = [n for n in z.namelist()
                   if n.endswith("/lean-arena-tests.tar.gz") or n == "lean-arena-tests.tar.gz"]
        assert len(members) == 1, members
        tar = out / "lean-arena-tests.tar.gz"
        tar.write_bytes(z.read(members[0]))
    fixtures = out / "fixtures"
    fixtures.mkdir(exist_ok=True)
    found = {}
    with tarfile.open(tar, "r:gz") as t:
        for member in t:
            if not member.isfile():
                continue
            parts = Path(member.name).parts
            assert len(parts) >= 2 and parts[0] in ("good", "bad")
            assert all(x not in ("", ".", "..") for x in parts)
            assert member.name.endswith(".ndjson")
            name = "/".join(parts[1:])[:-7]
            assert name in tests and name not in found, name
            meta = tests[name]
            expected = "accept" if parts[0] == "good" else "reject"
            assert meta["outcome"] == expected
            data = t.extractfile(member).read()
            assert len(data) == meta["size"]
            assert hashlib.sha256(data).hexdigest() == meta["sha256"], name
            dst = fixtures / (name + ".ndjson")
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            found[name] = dst
    small = {n for n, m in tests.items() if m.get("outcome") in ("accept", "reject")
             and m.get("size", 0) <= 10 * 1024 * 1024}
    prescribed = {n for n, m in tests.items() if m.get("outcome") in ("accept", "reject")}
    dump(out / "coverage.json", {
        "arena_revision": ARENA_REV, "source_run": RUN,
        "archive_sha256": sha(tar), "prescribed": len(prescribed),
        "portable": len(found), "uncovered": sorted(prescribed - set(found)),
        "missing_small": sorted(small - set(found)),
        "unexpected_small": sorted(set(found) - small)})
    assert set(found) == small, "Archive coverage mismatch; see coverage.json"
    # Names are used ONLY by the harness to verify exact fixture coverage,
    # never as checker input or to dispatch its behavior.
    assert SIX <= set(found), sorted(SIX - set(found))
    assert len(found) >= 190, "Unexpectedly incomplete current snapshot"
    return found

def config(out, threads=2):
    p = out / f"config-{threads}.json"
    dump(p, {"use_stdin": True, "nat_extension": True,
             "string_extension": True, "unpermitted_axiom_hard_error": False,
             "unsafe_permit_all_axioms": True, "num_threads": threads})
    return p

def commands(out, root):
    root = Path(root)
    cfg = config(out)
    return {
        "published": [str(root / "published/target/release/sokonanoda"), str(cfg)],
        "six_guard": [str(root / "stack/target/release/sokonanoda"), str(cfg)],
        "upstream_soko": [str(root / "soko/target/release/sokonanoda"),
                          "--stdin", "--nat-extension", "--string-extension",
                          "--axiom-allow-all", "--threads", "4"],
    }

def run_one(cmd, fixture, timeout, arm, log_dir, name, pmu=False):
    tag = arm + "-" + name.replace("/", "_")
    err = log_dir / (tag + ".stderr")
    stdout = log_dir / (tag + ".stdout")
    timing = log_dir / (tag + ".time")
    perf = log_dir / (tag + ".perf")
    full_cmd = ["/usr/bin/time", "-f", "%e %U %S %M", "-o", str(timing)]
    if pmu:
        full_cmd += ["perf", "stat", "-x,", "-o", str(perf), "-e", "instructions:u", "--"]
    full_cmd += cmd
    t0 = time.monotonic()
    try:
        with fixture.open("rb") as inp, err.open("wb") as e, stdout.open("wb") as o:
            p = subprocess.run(full_cmd, stdin=inp, stdout=o, stderr=e, timeout=timeout)
        raw = p.returncode
    except subprocess.TimeoutExpired:
        raw = "TIMEOUT"
    if raw == "TIMEOUT":
        arena = "timeout"
    elif raw == 0:
        arena = "accept"
    elif arm != "upstream_soko":
        # Exact current published Flash wrapper is '... || exit 1'.
        # Record raw status separately; do NOT confuse every panic with
        # a proven semantic rejection.
        arena = "reject" if raw != 0 else "accept"
    else:
        arena = {1: "reject", 2: "decline"}.get(raw, "error")
    row = {"arm": arm, "test": name, "raw_exit": raw, "arena_outcome": arena,
           "elapsed": round(time.monotonic() - t0, 4),
           "stderr_tail": err.read_bytes()[-1200:].decode(errors="replace"),
           "stdout_sha256": sha(stdout), "stderr_sha256": sha(err)}
    if timing.exists():
        row["time"] = timing.read_text().strip()
    if perf.exists():
        row["perf_raw"] = perf.read_text()
    return row

def classify(rows):
    return {
        "tested": len(rows),
        "wrong_accept": [r["test"] for r in rows
                         if r["expected"] == "reject" and r["arena_outcome"] == "accept"],
        "wrong_reject": [r["test"] for r in rows
                         if r["expected"] == "accept" and r["arena_outcome"] == "reject"],
        "nondecisive": [r["test"] for r in rows
                        if r["arena_outcome"] not in ("accept", "reject")],
        "raw_nonstandard_exit": [r["test"] for r in rows
                                 if r["raw_exit"] not in (0, 1, 2)],
        "correct": sum(r["arena_outcome"] == r["expected"] for r in rows)
    }

def portable(out, root):
    tests = source_manifest(out)
    fixtures = unpack_portable(out, tests)
    cmds = commands(out, root)
    logs = out / "logs"
    logs.mkdir()
    rows = []
    for name, fixture in sorted(fixtures.items()):
        expected = tests[name]["outcome"]
        timeout = int(tests[name].get("timeout") or 120)
        for arm, cmd in cmds.items():
            row = run_one(cmd, fixture, timeout, arm, logs, name)
            row["expected"] = expected
            row["input_sha256"] = tests[name]["sha256"]
            rows.append(row)
            print("ARENA_CASE", json.dumps({k: row[k] for k in
                  ("test", "arm", "expected", "raw_exit", "arena_outcome")}), flush=True)
        dump(out / "portable-rows.json", rows)
    summary = {arm: classify([r for r in rows if r["arm"] == arm]) for arm in cmds}
    baseline = {r["test"]: r for r in rows if r["arm"] == "published"}
    stack = {r["test"]: r for r in rows if r["arm"] == "six_guard"}
    summary["six_corrected"] = sorted(n for n in SIX
        if stack[n]["arena_outcome"] == "reject")
    summary["new_regression"] = sorted(n for n in fixtures
        if baseline[n]["arena_outcome"] == baseline[n]["expected"]
        and stack[n]["arena_outcome"] != stack[n]["expected"])
    summary["binary_sha256"] = {k: sha(v[0]) for k, v in cmds.items()}
    dump(out / "portable-summary.json", summary)
    print("ARENA_PORTABLE_SUMMARY", json.dumps(summary), flush=True)
    # A diagnostic with residuals is not a release-ready checker.
    s = summary["six_guard"]
    if s["wrong_accept"] or s["wrong_reject"] or s["nondecisive"]:
        raise SystemExit("Portable correctness residual remains; inspect preserved report")

def mathlib(out, root, fixture):
    tests = source_manifest(out)
    m = tests["mathlib"]
    assert fixture.stat().st_size == m["size"], (fixture.stat().st_size, m["size"])
    assert sha(fixture) == m["sha256"], "Regenerated Mathlib bytes differ from official input"
    dump(out / "mathlib-input.json", {"sha256": m["sha256"], "size": m["size"],
                                     "arena_revision": ARENA_REV, "source_run": RUN})
    cmds = commands(out, root)
    logs = out / "logs"
    logs.mkdir()
    probe = subprocess.run(["sh", "-c", "command -v perf >/dev/null && perf stat -e instructions:u -- true"],
                           capture_output=True)
    (out / "pmu-probe.txt").write_bytes(probe.stdout + probe.stderr)
    # Do not claim a hardware counter if the host denies access.
    pmu = probe.returncode == 0
    rows = []
    for i, arm in enumerate(["published", "six_guard", "upstream_soko",
                              "upstream_soko", "six_guard", "published"]):
        row = run_one(cmds[arm], fixture, 4120, arm, logs, f"mathlib-{i}", pmu)
        row["binary_sha256"] = sha(cmds[arm][0])
        row["input_sha256"] = m["sha256"]
        rows.append(row)
        dump(out / "mathlib-rows.json", rows)
        print("ARENA_MATHLIB", json.dumps(row), flush=True)
    if not all(r["raw_exit"] == 0 for r in rows):
        raise SystemExit("One or more exact current Mathlib replays failed")
    dump(out / "mathlib-summary.json", {"status": "MATCHED_CURRENT_MATHLIB_ACCEPT",
        "pmu_probe_permitted": pmu,
        "note": "Local timing/PMU only; not official leaderboard rank",
        "rows": rows})

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["portable", "mathlib"])
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--mathlib", type=Path)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.mode == "portable":
        portable(a.out, a.root)
    else:
        assert a.mathlib is not None
        mathlib(a.out, a.root, a.mathlib)
