#!/usr/bin/env python3
"""Independent source-pinned verdict parity and five-sample prune causal atlas.

Printed rows are diagnostic work counters, not instruction savings.
All input files originate from the pinned Arena portable export artifact.
"""
import hashlib
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
bins = {
    "source": "/tmp/prune-census-source.bin",
    "diagnostic": "/tmp/prune-census-diagnostic.bin",
}
opts = ["--stdin", "--nat-extension", "--string-extension",
        "--axiom-allow-all", "--threads", "1"]
good = sorted((root / "good").rglob("*.ndjson"))
bad = sorted((root / "bad").rglob("*.ndjson"))
assert len(good) == 125 and len(bad) == 71, (len(good), len(bad))
rows = []

def check(binary, path):
    with path.open("rb") as f:
        return subprocess.run(
            [binary, *opts], stdin=f,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=180
        )

for label, cases in [("good", good), ("bad", bad)]:
    for path in cases:
        outcome = {arm: check(binary, path).returncode
                   for arm, binary in bins.items()}
        assert outcome["source"] == outcome["diagnostic"], (str(path), outcome)
        rc = outcome["source"]
        assert (rc == 0 if label == "good" else rc in (1, 2)), (str(path), outcome)
        rows.append({"path": str(path.relative_to(root)), "returncode": rc})

counts = {"accepted": sum(r["returncode"] == 0 for r in rows),
          "rejected": sum(r["returncode"] == 1 for r in rows),
          "declined": sum(r["returncode"] == 2 for r in rows)}
assert counts == {"accepted": 125, "rejected": 69, "declined": 2}, counts
print("PRUNE_CENSUS_VERDICTS=" + json.dumps(
    {"total": len(rows), **counts, "identical": True, "wrong": 0}), flush=True)

names = ["init-prelude", "perf/grind-ring-5",
         "perf/magma-list-deep-n21", "perf/magma-list-pair-n7",
         "perf/fueled-chain"]

def parse_census(stderr: bytes):
    parts = []
    for raw in stderr.decode("utf-8", errors="replace").splitlines():
        if "MG_PRUNE_CENSUS_THREAD=" in raw:
            parts.append(json.loads(raw.split("MG_PRUNE_CENSUS_THREAD=", 1)[1]))
    assert parts, ("MISSING_THREAD_DROP_CENSUS", stderr[-1500:])
    keys = [k for k in parts[0] if k not in ("schema", "authority")]
    nums = {}
    for key in keys:
        if isinstance(parts[0][key], list):
            nums[key] = [sum(row[key][i] for row in parts)
                         for i in range(len(parts[0][key]))]
        else:
            nums[key] = sum(row[key] for row in parts)
    assert nums["cold"] == sum(nums["cold_mask_pop"]), nums
    assert nums["requests"] == sum(nums[k] for k in
        ("mask_zero", "from_nil", "frame_covers", "source_cell_hits",
         "direct_memo_hits", "cold")), nums
    assert nums["cold"] > 0 and nums["requests"] > 0
    return {"thread_count": len(parts), "counters": nums}

cases = []
for name in names:
    path = root / "good" / (name + ".ndjson")
    assert path.is_file()
    proc = check(bins["diagnostic"], path)
    assert proc.returncode == 0, (name, proc.returncode, proc.stderr[-2000:])
    x = parse_census(proc.stderr)
    c = x["counters"]
    row = {
        "case": name, "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        **x,
        "derived": {
            "cold_ratio": c["cold"] / c["requests"],
            "cached_ratio": (c["frame_covers"] + c["source_cell_hits"] +
                             c["direct_memo_hits"]) / c["requests"],
            "cold_far_fraction": c["far_cold"] / c["cold"],
            "cold_1near_fraction": c["cold_mask_pop"][1] / c["cold"],
            "cold_2near_fraction": c["cold_mask_pop"][2] / c["cold"],
            "average_cons_nodes_per_cold": c["nodes_cons"] / c["cold"],
            "average_frame_nodes_per_cold": c["nodes_frame"] / c["cold"],
            "average_skipped_cons_per_cold": c["skipped_cons"] / c["cold"],
            "average_copied_slots_per_cold": c["copied_slots"] / c["cold"],
            "frame_intern_hit_fraction": c["frame_intern_hits"] /
                max(1, c["frame_intern_hits"] + c["frame_intern_new"] +
                      c["frame_intern_hash_collisions"]),
        }
    }
    print("PRUNE_CENSUS_CASE=" + json.dumps(row), flush=True)
    cases.append(row)

report = {
    "authority": "pinned Sokonanoda 7645b1e, no proof-rule modifications",
    "source_basis": "sparse touched-slot + 4x PtrMap + env_extend singleprobe",
    "instrumentation": "thread-local work counters emitted on worker exit",
    "comparison": "original source checker versus instrumented same checker",
    "portable196": counts, "portable196_same": True,
    "sample_cases": cases,
    "claim": "causal cost distribution only; no Arena hardware instructions",
    "official_rank_qualified": False
}
(out / "prune-causal-census.json").write_text(json.dumps(report, indent=2) + "\n")
print("PRUNE_CENSUS_SUMMARY=" + json.dumps({
    "protected_verdicts": counts,
    "five_cases": len(cases),
    "total_cold": sum(x["counters"]["cold"] for x in cases),
    "total_requests": sum(x["counters"]["requests"] for x in cases),
    "official_rank_qualified": False
}), flush=True)
