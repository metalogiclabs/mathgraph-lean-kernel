#!/usr/bin/env python3
"""Validate and summarize Lean Refactor Arena JSONL inputs.

The organizer reference implementation consumes records with:
name, src, path, signature, contexts, proof_length, and header.
We fail closed on the fields needed to reproduce/refactor a theorem.
"""

from __future__ import annotations
import argparse, json
from pathlib import Path

REQUIRED = ("name", "src", "path", "signature")

def load(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path}:{n}: malformed JSON: {e}")
            missing = [k for k in REQUIRED if not row.get(k)]
            if missing:
                raise SystemExit(f"{path}:{n}: missing required fields: {missing}")
            if "contexts" in row and not isinstance(row["contexts"], list):
                raise SystemExit(f"{path}:{n}: contexts must be a list")
            rows.append(row)
    if not rows:
        raise SystemExit(f"{path}: no benchmark records")
    return rows

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--summary-out")
    args = ap.parse_args()
    rows = load(Path(args.jsonl))
    summary = {
        "schema": "mathgraph.lean-refactor-arena.official-input.v1",
        "count": len(rows),
        "names": [r["name"] for r in rows],
        "paths": sorted({r["path"] for r in rows}),
        "with_contexts": sum(bool(r.get("contexts")) for r in rows),
        "with_reported_proof_length": sum(r.get("proof_length") is not None for r in rows),
    }
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.summary_out:
        Path(args.summary_out).write_text(text, encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
