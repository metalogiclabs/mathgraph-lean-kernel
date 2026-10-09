#!/usr/bin/env python3
"""Bounded consequence-crossover candidates from already-evidenced Lean proofs.

This generator NEVER decides correctness, compatibility, or score. It preserves
the theorem's exact declaration prefix and exchanges whole named induction
branches between proof representations with that prefix. An unchanged source
proof is always retained as a control; all proposed crossovers are UNKNOWN
until the pinned Lean/Arena harness checks them. No source inference oracle or
LLM is used, and this script never changes the official submission packet.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
from collections import OrderedDict
from pathlib import Path

CASE = re.compile(r"^  case ([^\s=|]+).*=>\s*$")
TAIL = re.compile(r"^  all_goals(?:\s|$)")
FORBIDDEN = re.compile(
    r"\b(?:sorry|sorryAx|admit|axiom|native_decide|run_cmd|run_elab)\b"
    r"|#\s*(?:eval|reduce|exit)\b"
)


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def parse(proof: str) -> dict:
    if proof.count(" := by\n") != 1 or FORBIDDEN.search(proof):
        raise ValueError("unsupported theorem boundary or forbidden proof surface")
    lines = proof.splitlines(keepends=True)
    first = next((i for i, line in enumerate(lines) if CASE.match(line)), None)
    if first is None:
        raise ValueError("no named induction cases: decline crossover")
    prefix = "".join(lines[:first])
    header = proof.split(" := by\n", 1)[0]
    chunks: OrderedDict[str, str] = OrderedDict()
    end = len(lines)
    footer_start = next(
        (i for i in range(first, len(lines)) if TAIL.match(lines[i])), end
    )
    case_starts = [
        (i, CASE.match(lines[i]).group(1))
        for i in range(first, footer_start)
        if CASE.match(lines[i])
    ]
    if len(case_starts) != len(set(k for _, k in case_starts)):
        raise ValueError("duplicate named case: reject ambiguous decomposition")
    for j, (start, key) in enumerate(case_starts):
        stop = case_starts[j + 1][0] if j + 1 < len(case_starts) else footer_start
        chunks[key] = "".join(lines[start:stop])
    return {
        "header": header,
        "prefix": prefix,
        "chunks": chunks,
        "footer": "".join(lines[footer_start:]),
    }


def render(parsed: dict, patches: dict[str, str]) -> str:
    chunks = parsed["chunks"]
    return parsed["prefix"] + "".join(
        patches.get(key, value) for key, value in chunks.items()
    ) + parsed["footer"]


def crossover(rows: list[dict], *, max_candidates: int = 36) -> list[dict]:
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")
    if len(rows) < 2:
        raise ValueError("requires at least two declared parent proofs")
    names = {row["name"] for row in rows}
    labels = [row["label"] for row in rows]
    if len(names) != 1 or len(labels) != len(set(labels)):
        raise ValueError("parents must have identical theorem names and unique labels")
    parsed = {row["label"]: parse(row["proof"]) for row in rows}
    headers = {p["header"] for p in parsed.values()}
    preludes = {p["prefix"] for p in parsed.values()}
    if len(headers) != 1 or len(preludes) != 1:
        raise ValueError("different theorem/induction preludes: decline crossover")

    name = rows[0]["name"]
    accepted: list[dict] = []
    seen: set[str] = set()
    def add(label: str, proof: str, mechanism: str, source: list[str]) -> None:
        digest = sha256(proof)
        if digest in seen or len(accepted) >= max_candidates:
            return
        if not proof.startswith(parsed[labels[0]]["prefix"]):
            raise ValueError("statement boundary changed")
        seen.add(digest)
        accepted.append({
            "name": name,
            "label": label,
            "proof": proof,
            "mechanism": mechanism,
            "source_parents": source,
            "proof_sha256": digest,
            "status": "CANDIDATE_UNVERIFIED" if mechanism != "EXACT_PARENT_CONTROL"
                      else "PARENT_BYTES_UNMODIFIED__EVIDENCE_EXTERNAL",
        })
    for row in rows:
        add("control_" + re.sub(r"\W+", "_", row["label"]),
            row["proof"], "EXACT_PARENT_CONTROL", [row["label"]])

    for base, donor in itertools.permutations(rows, 2):
        a, b = parsed[base["label"]], parsed[donor["label"]]
        shared = [
            k for k in a["chunks"]
            if k in b["chunks"] and a["chunks"][k] != b["chunks"][k]
        ]
        btag = re.sub(r"\W+", "_", base["label"])
        dtag = re.sub(r"\W+", "_", donor["label"])
        for key in shared:
            proof = render(a, {key: b["chunks"][key]})
            add(f"splice_{btag}_{dtag}_{key}", proof,
                "NAMED_WITNESS_BRANCH_SUBSTITUTION", [base["label"], donor["label"]])
        for k1, k2 in itertools.combinations(shared, 2):
            proof = render(a, {k1: b["chunks"][k1], k2: b["chunks"][k2]})
            add(f"dual_{btag}_{dtag}_{k1}_{k2}", proof,
                "DUAL_BRANCH_CONSEQUENCE_CROSSOVER", [base["label"], donor["label"]])
        if a["footer"] != b["footer"]:
            proof = render({**a, "footer": b["footer"]}, {})
            add(f"footer_{btag}_{dtag}", proof,
                "TERMINAL_CONSEQUENCE_RECONSTRUCTION", [base["label"], donor["label"]])
    return accepted


def load(path: Path) -> list[dict]:
    result = []
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        row = json.loads(raw)
        if not all(isinstance(row.get(k), str) and row[k] for k in
                   ("name", "label", "proof")):
            raise ValueError(f"invalid row {i} in {path}")
        result.append(row)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parents", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--max-candidates", type=int, default=36)
    args = parser.parse_args()
    parents = [x for x in load(Path(args.parents)) if x["name"] == args.name]
    variants = crossover(parents, max_candidates=args.max_candidates)
    Path(args.out).write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in variants),
        encoding="utf-8",
    )
    manifest = {
        "schema": "mathgraph.lra.consequence-crossover.v1",
        "status": "CANDIDATE_GENERATION__NO_LEAN_VERDICT",
        "name": args.name,
        "parents": [{"label": p["label"], "sha256": sha256(p["proof"])}
                    for p in parents],
        "candidates": len(variants),
        "control_count": sum(v["mechanism"] == "EXACT_PARENT_CONTROL" for v in variants),
        "candidate_sha256": [v["proof_sha256"] for v in variants],
        "protected": "exact theorem declaration and common induction prelude",
        "not_authorized": ["proof correctness", "version survival",
                           "score improvement", "portfolio mutation"],
    }
    Path(args.manifest).write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: v for k, v in manifest.items()
                      if k != "candidate_sha256"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
