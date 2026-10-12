#!/usr/bin/env python3
"""Bounded developmental compiler for conversion scheduling policies.

Input JSONL records contain only structural state features and per-action
consequences. Benchmark/test identities are optional metadata and are never used
as policy features.

Each record has:
  state: dict[str, bool|int|str]
  actions: dict[action_name, {"correct": bool, "cost": float}]

The compiler searches a deliberately small policy class: a default action plus
up to two ordered predicate/action exceptions. Selection is lexicographic:
  1. zero semantic errors
  2. maximum number of records where a correct action is chosen
  3. minimum total cost
  4. minimum policy description length

This is the first bounded version of the MSI conversion-policy experiment.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from itertools import product
from pathlib import Path
from typing import Any, Iterable


GENERIC_ACTIONS = (
    "compare_args",
    "unfold_left",
    "unfold_right",
    "unfold_both",
    "structural",
)

# Generic predicates only. No benchmark/test names are permitted here.
PREDICATES = (
    "left_shorter",
    "right_shorter",
    "one_spine_is_one",
    "heads_match",
    "left_unfoldable",
    "right_unfoldable",
    "proof_valued",
    "forced_mismatch",
    "shared_subproblem",
)


@dataclass(frozen=True)
class Clause:
    predicate: str
    action: str


@dataclass(frozen=True)
class Policy:
    default: str
    clauses: tuple[Clause, ...] = ()

    def choose(self, state: dict[str, Any]) -> str:
        for c in self.clauses:
            if bool(state.get(c.predicate, False)):
                return c.action
        return self.default

    @property
    def mdl(self) -> int:
        return 1 + 2 * len(self.clauses)


@dataclass
class Score:
    semantic_errors: int
    covered: int
    total_cost: float
    mdl: int

    def key(self) -> tuple[int, int, float, int]:
        return (self.semantic_errors, -self.covered, self.total_cost, self.mdl)


def load_records(path: Path) -> list[dict[str, Any]]:
    out = []
    with path.open() as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if "state" not in rec or "actions" not in rec:
                raise ValueError(f"{path}:{i}: expected state/actions")
            out.append(rec)
    if not out:
        raise ValueError("no records")
    return out


def score(policy: Policy, records: Iterable[dict[str, Any]]) -> Score:
    errors = covered = 0
    cost = 0.0
    for r in records:
        a = policy.choose(r["state"])
        outcome = r["actions"].get(a)
        if outcome is None:
            errors += 1
            cost += 1e30
            continue
        ok = bool(outcome.get("correct", False))
        errors += int(not ok)
        covered += int(ok)
        cost += float(outcome.get("cost", 1e30))
    return Score(errors, covered, cost, policy.mdl)


def enumerate_policies(actions: tuple[str, ...], predicates: tuple[str, ...], max_clauses: int):
    for d in actions:
        yield Policy(d)
    if max_clauses >= 1:
        for p, a, d in product(predicates, actions, actions):
            yield Policy(d, (Clause(p, a),))
    if max_clauses >= 2:
        for p1, p2 in product(predicates, predicates):
            if p1 == p2:
                continue
            for a1, a2, d in product(actions, actions, actions):
                yield Policy(d, (Clause(p1, a1), Clause(p2, a2)))


def compile_policy(records: list[dict[str, Any]], max_clauses: int = 2) -> tuple[Policy, Score]:
    actions = tuple(a for a in GENERIC_ACTIONS if any(a in r["actions"] for r in records))
    predicates = tuple(p for p in PREDICATES if any(p in r["state"] for r in records))
    if not actions:
        raise ValueError("no supported actions in records")
    best = None
    for p in enumerate_policies(actions, predicates, max_clauses):
        s = score(p, records)
        if best is None or s.key() < best[1].key():
            best = (p, s)
    assert best is not None
    return best


def policy_json(policy: Policy, score_: Score) -> dict[str, Any]:
    return {
        "default": policy.default,
        "clauses": [asdict(c) for c in policy.clauses],
        "score": asdict(score_),
        "policy_mdl": policy.mdl,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("records", type=Path)
    ap.add_argument("--sealed", type=Path)
    ap.add_argument("--max-clauses", type=int, default=2, choices=(0, 1, 2))
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    train = load_records(args.records)
    policy, train_score = compile_policy(train, args.max_clauses)
    result = {"policy": policy_json(policy, train_score), "train_records": len(train)}

    if args.sealed:
        sealed = load_records(args.sealed)
        result["sealed_records"] = len(sealed)
        result["sealed_score"] = asdict(score(policy, sealed))

    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")


if __name__ == "__main__":
    main()
