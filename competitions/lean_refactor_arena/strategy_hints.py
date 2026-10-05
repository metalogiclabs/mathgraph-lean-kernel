#!/usr/bin/env python3
"""Cheap generic strategy routing for Lean Refactor Arena tasks.

This does not generate a proof.  It recognizes structural pressure in the
frozen statement/reference and returns a small set of representation moves to
try before unconstrained generation.  No warm-up theorem names or solutions are
encoded, so it is usable on hidden tasks.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

from official_jsonl import load

def route(row: dict) -> list[dict]:
    stmt = str(row.get("statement") or row.get("signature") or "")
    src = str(row.get("src") or "")
    proof = src[len(stmt):] if src.startswith(stmt) else src
    out: list[tuple[str,str]] = []

    def add(strategy: str, reason: str) -> None:
        if strategy not in {x[0] for x in out}:
            out.append((strategy, reason))

    if ".Subset" in stmt or "⊆" in stmt:
        add("POINTWISE_FUTURE", "the protected conclusion is inclusion; pointwise membership may be the smaller present")
        if "++" in stmt or "∪" in stmt or proof.count("Subset.trans") + proof.count("Subset.app") >= 2:
            add("PROSPECTIVE_CODOMAIN", "recursive inclusion is composed through append/union or repeated transitivity")

    witness_words = ("Normalized", "WellFormed", ".WF", "Typing", "Valid", "Value")
    if "→" in stmt and any(w in stmt for w in witness_words):
        add("WITNESS_FIRST", "the statement exposes a proof-bearing structural witness")

    if "Diamond" in stmt or any(w in stmt for w in ("progress", "bisim", "Simulation", "simulation")):
        add("DERIVATION_INDUCTION", "the theorem protects future reductions/transitions")

    if "∃" in stmt and any(w in src for w in ("updatedState", "updatedStates", "UpdateState", "UpdateStates", "InitState", "InitStates")):
        add("SEMANTIC_RECONSTRUCTION", "the goal asks for a canonical witness and the environment exposes update/commutation laws")

    if "Submodule.span" in src or "span_induction" in proof:
        add("BASIS_QUOTIENT", "the proof is closed under linear span constructors")

    if ("= 0" in stmt or "=0" in stmt) and (
        "IsTestFunction" in stmt or re.search(r"∀\s+\w+\s*,", stmt)
    ):
        add("SEPARATING_WITNESS", "a universal testing hypothesis may be contradicted by one localized separating probe")

    if any(w in stmt.lower() for w in ("period", "recurrence")) or (
        "bounded" in stmt.lower() and proof.count("induction") > 0
    ):
        add("MINIMAL_STATE_INVARIANT", "a bounded/recursive future may be controlled by a finite sufficient state")

    algebra_ops = proof.count("rw [") + proof.count("calc") + proof.count("ring") + proof.count("field_simp")
    if "=" in stmt and algebra_ops >= 6:
        add("LOCAL_ALGEBRAIC_FACTOR", "the reference has a large equality-normalization surface")

    if proof.count("induction") and not any(s=="WITNESS_FIRST" for s,_ in out):
        add("SEMANTIC_RECONSTRUCTION", "the reference pays for induction; first test whether a canonical environmental law removes it")

    return [{"strategy": s, "reason": r} for s,r in out[:4]]

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--name")
    args=ap.parse_args()
    rows=load(Path(args.benchmark))
    if args.name:
        rows=[r for r in rows if r["name"]==args.name]
        if len(rows)!=1:
            raise SystemExit("expected exactly one named benchmark row")
    for row in rows:
        print(json.dumps({
            "name":row["name"],
            "source":row.get("source"),
            "proof_length":row.get("proof_length"),
            "hints":route(row),
        },ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
