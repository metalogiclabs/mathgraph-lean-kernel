#!/usr/bin/env python3
"""Zero-change and candidate artifact controls for the Lean Refactor Arena.

This module intentionally separates *our* auditable run artifact from the final
Arena upload encoding. The live Space's submission parser is inspected and
pinned separately; no optimizer is allowed to mutate problem identity.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from official_jsonl import identity, load, relative_path, schema_of


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def baseline(input_path: Path, output_path: Path) -> None:
    src_rows = load(input_path)
    out = []
    for row in src_rows:
        original_len = row.get("proof_length")
        out.append({
            "name": row["name"],
            "source": row.get("source", ""),
            "file_path": relative_path(row),
            "input_schema": schema_of(row),
            "original_proof_length": original_len,
            "optimized_proof_length": original_len,
            "reduction_percentage": 0.0,
            "original_proof": row["src"],
            "proof": row["src"],
            "control": "zero_change",
        })
    write_jsonl(output_path, out)
    print(f"ZERO_CHANGE_BASELINE_WRITTEN count={len(out)} path={output_path}")


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line_no, raw in enumerate(f, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: malformed JSON: {exc}")
            rows.append(row)
    return rows


def output_identity(row: dict) -> tuple[str, str]:
    return str(row.get("name") or ""), str(row.get("source") or row.get("file_path") or "")


def validate(input_path: Path, output_path: Path, require_control_identity: bool) -> None:
    source = load(input_path)
    output = read_jsonl(output_path)

    source_keys = [identity(r) for r in source]
    output_keys = [output_identity(r) for r in output]
    if len(set(output_keys)) != len(output_keys):
        raise SystemExit("output contains duplicate Arena identities")
    if source_keys != output_keys:
        raise SystemExit(
            f"output identities/order differ from benchmark input: "
            f"input={source_keys} output={output_keys}"
        )

    for i, (src, out) in enumerate(zip(source, output, strict=True), 1):
        if not isinstance(out.get("proof"), str) or not out["proof"].strip():
            raise SystemExit(f"row {i}: missing proof")
        if out.get("original_proof") != src["src"]:
            raise SystemExit(f"row {i}: original_proof is not the frozen organizer source")
        if require_control_identity and out["proof"] != src["src"]:
            raise SystemExit(f"row {i}: zero-change control mutated the proof")
        if require_control_identity and out.get("reduction_percentage") != 0.0:
            raise SystemExit(f"row {i}: zero-change control claims a gain")

    mode = "ZERO_CHANGE_IDENTITY" if require_control_identity else "CANDIDATE_ARTIFACT"
    print(f"VERIFIED_{mode} count={len(output)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("baseline")
    b.add_argument("--input", required=True)
    b.add_argument("--output", required=True)

    v = sub.add_parser("validate")
    v.add_argument("--input", required=True)
    v.add_argument("--output", required=True)
    v.add_argument("--require-control-identity", action="store_true")

    args = ap.parse_args()
    if args.cmd == "baseline":
        baseline(Path(args.input), Path(args.output))
    else:
        validate(
            Path(args.input),
            Path(args.output),
            bool(args.require_control_identity),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
