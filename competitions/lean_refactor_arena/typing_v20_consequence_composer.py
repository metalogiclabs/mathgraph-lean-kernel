#!/usr/bin/env python3
"""Exact, bounded constructor-observer composition for Typing V20.

This is a SOURCE-EXACT reconstruction check, not a Lean proof checker.

It composes four individually primary-checked local source contractions:
T (type-application witness inline), C (sum-case observer simplification),
L/R (specific reduction-constructor hints). The L/R operators are defined
on tactic argument atoms, rather than overlapping character spans.

Every generated proof must match a separately frozen V20 source row byte for
byte. Actual soundness and cost are established ONLY by pinned Lean evidence:
https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38004209274

No automatic admission or inference beyond this theorem/grammar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

TARGET = "Cslib.LambdaCalculus.LocallyNameless.Fsub.Typing.progress"
SOURCE_PIN = "7f3a401470d04f70013d293db4253b088ec8a0ae"
PRIMARY_RUN = 38004209274
BITS = "TCLR"
MASKS = ("", "T", "C", "L", "R", "TC", "TL", "TR",
         "CL", "CR", "LR", "TCL", "TCR", "TLR", "CLR", "TCLR")
PREFIX = "typing_v20_compound_"
CONTROL = "typing_v20_exact_308_control"


def read_bank(path: Path) -> dict[str, str]:
    rows = [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]
    assert len(rows) == len(MASKS), "WRONG_FROZEN_CANDIDATE_COUNT"
    assert len({r["label"] for r in rows}) == len(rows), "DUPLICATED_LABEL"
    assert all(r["name"] == TARGET for r in rows), "WRONG_THEOREM"
    bank = {r["label"]: r["proof"] for r in rows}
    expected = {CONTROL} | {PREFIX + m for m in MASKS if m}
    assert set(bank) == expected, "WRONG_FROZEN_MASK_SET"
    assert len(set(bank.values())) == len(bank), "DUPLICATED_PROOF_BYTES"
    return bank


def contiguous_edit(a: str, b: str) -> tuple[str, str]:
    """Find the minimal one-interval edit between the shared source and an operator."""
    start = 0
    while start < min(len(a), len(b)) and a[start] == b[start]:
        start += 1
    ea, eb = len(a), len(b)
    while ea > start and eb > start and a[ea - 1] == b[eb - 1]:
        ea -= 1
        eb -= 1
    before, after = a[start:ea], b[start:eb]
    assert before != after, "NO_OPERATOR_CONTRACTION"
    return before, after


def replace_once(text: str, old: str, new: str) -> str:
    assert old and text.count(old) == 1, "NONUNIQUE_OR_MISSING_ANCHOR"
    return text.replace(old, new, 1)


def constructor_line(proof: str) -> str:
    hits = [line for line in proof.splitlines()
            if line.strip().startswith("all_goals solve_by_elim [Or.inl")]
    assert len(hits) == 1, "CONSTRUCTOR_OBSERVER_NOT_UNIQUE"
    return hits[0]


def compile_mask(control: str, t_edit: tuple[str, str],
                 c_edit: tuple[str, str], mask: str) -> str:
    assert mask == "".join(ch for ch in BITS if ch in mask), "NONCANONICAL_MASK"
    proof = control
    if "T" in mask:
        proof = replace_once(proof, *t_edit)
    if "C" in mask:
        proof = replace_once(proof, *c_edit)

    if "L" in mask or "R" in mask:
        line = constructor_line(proof)
        opening = line.index("[")
        closing = line.rindex("]")
        args = line[opening + 1:closing].split(", ")
        assert len(args) == len(set(args)), "OBSERVER_MULTIPLICITY_AMBIGUITY"
        assert "Red.inl" in args and "Red.inr" in args, "MISSING_CONSTRUCTOR_WITNESS"
        removed = {"Red.inl" if "L" in mask else "", "Red.inr" if "R" in mask else ""}
        remaining = [atom for atom in args if atom not in removed]
        new_line = line[:opening + 1] + ", ".join(remaining) + line[closing:]
        proof = replace_once(proof, line, new_line)
    return proof


def verify(bank: dict[str, str]) -> dict:
    original = bank[CONTROL]
    header = original.split(" := by\n", 1)[0] + " := by\n"
    assert all(p.startswith(header) for p in bank.values()), "STATEMENT_CHANGED"
    t_edit = contiguous_edit(original, bank[PREFIX + "T"])
    c_edit = contiguous_edit(original, bank[PREFIX + "C"])

    results = []
    for mask in MASKS:
        label = CONTROL if not mask else PREFIX + mask
        produced = compile_mask(original, t_edit, c_edit, mask)
        expected = bank[label]
        assert produced == expected, "COMPOSITION_NOT_SOURCE_EXACT:" + label
        assert not any(word in produced for word in ("sorryAx", "sorry", "admit", "native_decide", "run_elab"))
        results.append({
            "mask": mask or "identity", "label": label,
            "proof_sha256": hashlib.sha256(produced.encode("utf-8")).hexdigest(),
            "matches_frozen_bytes": True,
        })
    return {
        "schema": "mathgraph.lra.typing.v20.source-exact-consequence-composition.v1",
        "state": "VERIFIED_FROZEN_SYNTACTIC_COMPOSITION__LEAN_AUTHORITY_SEPARATE",
        "source_pin": SOURCE_PIN,
        "theorem": TARGET,
        "upstream_primary_run": PRIMARY_RUN,
        "operator_axes": {
            "T": "specific type-application witness inlining",
            "C": "specific sum-case observer contraction",
            "L": "remove one redundant Red.inl constructor hint",
            "R": "remove one redundant Red.inr constructor hint",
        },
        "verified_composites": len(results),
        "required_composites": len(MASKS),
        "results": results,
        "scope": "only frozen Typing proof bank under pinned upstream source",
        "never_claims": ["new Lean verification", "universal commuting operators",
                         "all-version compatibility", "official score"],
        "portfolio_mutated": False,
        "officially_submitted": False,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bank", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    result = verify(read_bank(args.bank))
    args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "results"},
                     indent=2, ensure_ascii=False))
    print("VERIFIED_FROZEN_TYPING_V20_CONSEQUENCE_COMPOSITION_16_OF_16")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
