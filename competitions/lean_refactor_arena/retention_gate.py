#!/usr/bin/env python3
"""Reproduce Lean Refactor Arena per-problem scoring and gate retention.

The live leaderboard scores a compiled theorem on the mean of:
  length reduction %, heartbeat reduction %, zero-shot compatibility %.

MathGraph adds a stricter developmental constraint: a candidate is not retained
unless it preserves every listed compatibility target. A leaderboard gain may
not buy compatibility loss.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from official_jsonl import load
from submission import read_jsonl


def find_benchmark(rows: list[dict], name: str) -> dict:
    xs = [r for r in rows if r["name"] == name]
    if len(xs) != 1:
        raise SystemExit(f"expected exactly one benchmark row named {name!r}")
    return xs[0]


def heartbeat_map(path: Path) -> dict[str, int]:
    return {
        str(r["name"]): int(r["heartbeat"])
        for r in read_jsonl(path)
    }


def score(
    original_length: int,
    candidate_length: int,
    original_heartbeat: int,
    candidate_heartbeat: int,
    compat_passed: int,
    compat_total: int,
) -> dict:
    if original_length <= 0 or original_heartbeat <= 0 or compat_total <= 0:
        raise ValueError("invalid non-positive scoring denominator")
    if not (0 <= compat_passed <= compat_total):
        raise ValueError("compat_passed must be between 0 and compat_total")

    length_pct = (original_length - candidate_length) / original_length * 100.0
    heartbeat_pct = (
        (original_heartbeat - candidate_heartbeat) / original_heartbeat * 100.0
    )
    compat_pct = compat_passed / compat_total * 100.0
    combined = (length_pct + heartbeat_pct + compat_pct) / 3.0

    baseline_length_pct = 0.0
    baseline_heartbeat_pct = 0.0
    baseline_compat_pct = 100.0
    baseline = (
        baseline_length_pct + baseline_heartbeat_pct + baseline_compat_pct
    ) / 3.0

    strict_compatibility_preserved = compat_passed == compat_total
    retained = strict_compatibility_preserved and combined > baseline + 1e-12

    return {
        "length_reduction_pct": length_pct,
        "heartbeat_reduction_pct": heartbeat_pct,
        "compatibility_pct": compat_pct,
        "combined_pct": combined,
        "zero_change_baseline_pct": baseline,
        "delta_vs_zero_change_baseline_pct": combined - baseline,
        "strict_compatibility_preserved": strict_compatibility_preserved,
        "retain": retained,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--heartbeats", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--candidate-length", type=int, required=True)
    ap.add_argument("--candidate-heartbeat", type=int, required=True)
    ap.add_argument("--compat-passed", type=int, required=True)
    ap.add_argument("--compat-total", type=int, required=True)
    ap.add_argument("--out")
    ap.add_argument("--require-retain", action="store_true")
    args = ap.parse_args()

    row = find_benchmark(load(Path(args.benchmark)), args.name)
    hbs = heartbeat_map(Path(args.heartbeats))
    if args.name not in hbs:
        raise SystemExit(f"no published heartbeat for {args.name}")

    result = {
        "schema": "mathgraph.lean-refactor-arena.retention.v1",
        "name": args.name,
        "original_proof_length": int(row["proof_length"]),
        "candidate_proof_length": args.candidate_length,
        "original_heartbeat": hbs[args.name],
        "candidate_heartbeat": args.candidate_heartbeat,
        "compat_passed": args.compat_passed,
        "compat_total": args.compat_total,
    }
    result.update(
        score(
            result["original_proof_length"],
            result["candidate_proof_length"],
            result["original_heartbeat"],
            result["candidate_heartbeat"],
            args.compat_passed,
            args.compat_total,
        )
    )

    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")

    if result["retain"]:
        print("VERIFIED_SCORE_EARNING_RETENTION")
    else:
        print("CANDIDATE_NOT_RETAINED")
        if args.require_retain:
            raise SystemExit("candidate did not beat the zero-change floor while preserving compatibility")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
