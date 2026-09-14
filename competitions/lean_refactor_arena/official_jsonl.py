#!/usr/bin/env python3
"""Validate and normalize Lean Refactor Arena JSONL inputs.

Two public surfaces currently exist:
1. the live warm-up payload served by the Arena Space;
2. the extraction/optimizer schema used by delta-lab-ai/lean-refactor.

The live payload is authoritative for competition work. We support the optimizer
schema as an adapter, but never require fields that the live benchmark omits.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path


def schema_of(row: dict) -> str:
    if {"source", "statement", "file_path", "version_info"}.issubset(row):
        return "live_warmup"
    if {"path", "signature"}.issubset(row):
        return "optimizer"
    return "unknown"


def identity(row: dict) -> tuple[str, str]:
    # Source is stable across the live benchmark; path is used by optimizer data.
    namespace = str(row.get("source") or row.get("path") or "")
    return str(row.get("name") or ""), namespace


def relative_path(row: dict) -> str:
    return str(row.get("file_path") if "file_path" in row else row.get("path") or "")


def statement(row: dict) -> str:
    return str(row.get("statement") or row.get("signature") or "")


def validate_row(path: Path, line_no: int, row: dict) -> None:
    schema = schema_of(row)
    if schema == "unknown":
        raise SystemExit(
            f"{path}:{line_no}: unrecognized Arena schema; keys={sorted(row)}"
        )

    common = ["name", "src"]
    missing = [k for k in common if not row.get(k)]
    if missing:
        raise SystemExit(f"{path}:{line_no}: missing required fields: {missing}")

    if not statement(row).strip():
        raise SystemExit(f"{path}:{line_no}: missing theorem statement/signature")

    if schema == "live_warmup":
        required_present = [
            "source", "proof_length", "num_lines", "header",
            "file_path", "version_info"
        ]
        absent = [k for k in required_present if k not in row]
        if absent:
            raise SystemExit(f"{path}:{line_no}: missing live fields: {absent}")
        if not isinstance(row["version_info"], list) or not row["version_info"]:
            raise SystemExit(f"{path}:{line_no}: version_info must be a nonempty list")
        for v in row["version_info"]:
            if not isinstance(v, dict) or len(v) != 1:
                raise SystemExit(
                    f"{path}:{line_no}: each version_info entry must be one mapping"
                )
    else:
        if "contexts" in row and not isinstance(row["contexts"], list):
            raise SystemExit(f"{path}:{line_no}: contexts must be a list")


def load(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line_no, raw in enumerate(f, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: malformed JSON: {exc}")
            validate_row(path, line_no, row)
            rows.append(row)

    if not rows:
        raise SystemExit(f"{path}: no benchmark records")

    ids = [identity(r) for r in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit(f"{path}: duplicate Arena identities")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--summary-out")
    args = ap.parse_args()

    path = Path(args.jsonl)
    rows = load(path)
    schemas = collections.Counter(schema_of(r) for r in rows)
    sources = collections.Counter(str(r.get("source") or "") for r in rows)
    version_counts = [
        len(r.get("version_info", [])) for r in rows if schema_of(r) == "live_warmup"
    ]
    lengths = [
        int(r["proof_length"]) for r in rows if r.get("proof_length") is not None
    ]

    summary = {
        "schema": "mathgraph.lean-refactor-arena.input-summary.v2",
        "count": len(rows),
        "schemas": dict(schemas),
        "sources": dict(sources),
        "names": [r["name"] for r in rows],
        "paths": [relative_path(r) for r in rows],
        "blank_paths": sum(not relative_path(r) for r in rows),
        "proof_length_min": min(lengths) if lengths else None,
        "proof_length_max": max(lengths) if lengths else None,
        "version_targets_min": min(version_counts) if version_counts else None,
        "version_targets_max": max(version_counts) if version_counts else None,
    }
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.summary_out:
        Path(args.summary_out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
