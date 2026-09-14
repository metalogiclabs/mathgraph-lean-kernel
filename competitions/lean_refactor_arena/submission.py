#!/usr/bin/env python3
"""Submission-shape controls for the Lean Refactor Arena.

The zero-change baseline is intentionally boring: it emits each organizer input
proof unchanged. That gives us a control artifact whose ordering, identity, and
record coverage can be checked before any optimizer is introduced.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from official_jsonl import load


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
            "path": row["path"],
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


def validate(input_path: Path, output_path: Path, require_control_identity: bool) -> None:
    source = load(input_path)
    output = read_jsonl(output_path)

    source_keys = [(r["name"], r["path"]) for r in source]
    output_keys = [(r.get("name"), r.get("path")) for r in output]
    if len(set(source_keys)) != len(source_keys):
        raise SystemExit("input contains duplicate (name,path) identities")
    if len(set(output_keys)) != len(output_keys):
        raise SystemExit("output contains duplicate (name,path) identities")
    if source_keys != output_keys:
        raise SystemExit("output identities/order differ from organizer input")

    for i, (src, out) in enumerate(zip(source, output, strict=True), 1):
        if not isinstance(out.get("proof"), str) or not out["proof"].strip():
            raise SystemExit(f"row {i}: missing proof")
        if out.get("original_proof") != src["src"]:
            raise SystemExit(f"row {i}: original_proof is not the frozen organizer source")
        if require_control_identity and out["proof"] != src["src"]:
            raise SystemExit(f"row {i}: zero-change control mutated the proof")
        if require_control_identity and out.get("reduction_percentage") != 0.0:
            raise SystemExit(f"row {i}: zero-change control claims a gain")

    mode = "ZERO_CHANGE_IDENTITY" if require_control_identity else "SUBMISSION_SHAPE"
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
