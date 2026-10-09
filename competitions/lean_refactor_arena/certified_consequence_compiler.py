#!/usr/bin/env python3
"""Fail-closed proof consequence-operator candidate compiler.

A certified operator can recreate exact previously verified proof bytes.
It NEVER generalizes a version-specific warrant to a different proof,
statement, theorem, import environment, or future benchmark. A generated
candidate must be checked by the organizer's pinned Lean harness before
it can enter a retained portfolio.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

BOUNDARY = " := by\n"
FORBIDDEN = re.compile(
    r"\b(?:sorry|sorryAx|admit|axiom|unsafe|native_decide|run_cmd|run_elab)\b"
    r"|#\s*(?:eval|reduce|exit)\b|\bIO\."
)


def digest(proof: str) -> str:
    return hashlib.sha256(proof.encode("utf-8")).hexdigest()


def declaration(proof: str) -> str:
    idx = proof.find(BOUNDARY)
    if idx < 1:
        raise ValueError("NO_THEOREM_DECLARATION_BOUNDARY")
    return proof[:idx + len(BOUNDARY)]


def jsonl(path: Path) -> list[dict]:
    result: list[dict] = []
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        x = json.loads(raw)
        if not isinstance(x, dict):
            raise ValueError(f"INVALID_JSONL_ROW:{i}")
        result.append(x)
    return result


def _check_source(row: dict) -> None:
    if not all(isinstance(row.get(k), str) and row[k] for k in ("name", "label", "proof")):
        raise ValueError("INCOMPLETE_PROTECTED_PROOF_ROW")
    declaration(row["proof"])
    if FORBIDDEN.search(row["proof"]):
        raise ValueError("FORBIDDEN_PROTECTED_PROOF_SURFACE")


def _check_rule(op: dict) -> None:
    fields = ("id", "theorem", "anchor_before", "replacement_after",
              "source_proof_sha256", "certified_proof_sha256",
              "verifier_pin", "operator_family")
    if not all(isinstance(op.get(k), str) and op[k] for k in fields):
        raise ValueError("MISSING_OPERATOR_AUTHORITY")
    if not isinstance(op.get("protected_future"), list) or not op["protected_future"]:
        raise ValueError("MISSING_PROTECTED_FUTURE")
    if len(op["protected_future"]) != len(set(op["protected_future"])):
        raise ValueError("DUPLICATE_PROTECTED_VERSION")
    if not isinstance(op.get("verifier_run"), int) or op["verifier_run"] <= 0:
        raise ValueError("MISSING_VERIFIER_RUN")
    if FORBIDDEN.search(op["replacement_after"]):
        raise ValueError("FORBIDDEN_GENERATED_PROOF_SURFACE")


def compile_bank(rows: list[dict], operators: list[dict],
                 *, max_candidates: int = 100) -> tuple[list[dict], dict]:
    if not 1 <= max_candidates <= 1000:
        raise ValueError("INVALID_CANDIDATE_BUDGET")
    if len({(x.get("name"), x.get("label")) for x in rows}) != len(rows):
        raise ValueError("DUPLICATE_SOURCE_IDENTITY")
    if len({op.get("id") for op in operators}) != len(operators):
        raise ValueError("DUPLICATE_OPERATOR_ID")
    for op in operators:
        _check_rule(op)
    candidates = []
    declines = []
    controls = []
    seen = set()

    for row in rows:
        _check_source(row)
        proof = row["proof"]
        sha = digest(proof)
        versions = row.get("required_versions")
        if not isinstance(versions, list) or not versions:
            raise ValueError("SOURCE_WITHOUT_REQUIRED_VERSIONS")
        baseline = {
            "name": row["name"], "label": "control_" + row["label"],
            "proof": proof, "required_versions": versions,
            "proof_sha256": sha, "status": "EXACT_CONTROL_NO_NEW_WARRANT",
        }
        controls.append(baseline)
        seen.add((row["name"], sha))
        for op in operators:
            if op["theorem"] != row["name"]:
                continue
            reason = None
            if sorted(op["protected_future"]) != sorted(versions):
                reason = "PROTECTED_FUTURE_MISMATCH"
            elif sha != op["source_proof_sha256"]:
                reason = "SOURCE_PROOF_HASH_MISMATCH"
            elif proof.count(op["anchor_before"]) != 1:
                reason = "NON_UNIQUE_OR_ABSENT_OPERATOR_ANCHOR"
            elif len(candidates) + 1 > max_candidates:
                reason = "BOUNDED_BUDGET_EXHAUSTED"

            if reason:
                declines.append({"theorem": row["name"], "operator": op["id"],
                                 "reason": reason})
                continue
            candidate = proof.replace(op["anchor_before"], op["replacement_after"], 1)
            if candidate == proof:
                declines.append({"theorem": row["name"], "operator": op["id"],
                                 "reason": "NO_CONSEQUENTIAL_CHANGE"})
                continue
            if declaration(candidate) != declaration(proof):
                declines.append({"theorem": row["name"], "operator": op["id"],
                                 "reason": "THEOREM_STATEMENT_CHANGED"})
                continue
            if FORBIDDEN.search(candidate):
                declines.append({"theorem": row["name"], "operator": op["id"],
                                 "reason": "FORBIDDEN_CANDIDATE_SURFACE"})
                continue
            candidate_sha = digest(candidate)
            if (row["name"], candidate_sha) in seen:
                declines.append({"theorem": row["name"], "operator": op["id"],
                                 "reason": "DUPLICATE_OBSERVATIONAL_CANDIDATE_BYTES"})
                continue
            seen.add((row["name"], candidate_sha))
            exact_prior = candidate_sha == op["certified_proof_sha256"]
            candidates.append({
                "name": row["name"], "label": "operator_" + op["id"],
                "proof": candidate, "required_versions": versions,
                "source_proof_sha256": sha, "proof_sha256": candidate_sha,
                "operator_id": op["id"], "mechanism": op["operator_family"],
                "verifier_pin": op["verifier_pin"],
                "historical_exact_certificate_match": exact_prior,
                "historical_run": op["verifier_run"] if exact_prior else None,
                "status": "CANDIDATE_UNVERIFIED_FOR_NEW_ADMISSION",
            })
    manifest = {
        "schema": "mathgraph.lra.certified-consequence-compiler.v1",
        "status": "BOUNDED_CANDIDATE_GENERATION_NO_AUTOMATIC_ADMISSION",
        "controls": len(controls), "proposals": len(candidates),
        "declined": declines,
        "exact_prior_certificate_matches": sum(
            x["historical_exact_certificate_match"] for x in candidates),
        "protected": ["theorem statement", "source proof hash",
                      "required Lean versions", "forbidden surface",
                      "no implicit verifier warrant"],
        "portfolio_mutated": False,
        "official_submission": False,
    }
    return controls + candidates, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--operators", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--max-candidates", type=int, default=100)
    args = parser.parse_args()
    bank, meta = compile_bank(jsonl(args.sources), jsonl(args.operators),
                              max_candidates=args.max_candidates)
    args.out.write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in bank),
        encoding="utf-8")
    args.manifest.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
