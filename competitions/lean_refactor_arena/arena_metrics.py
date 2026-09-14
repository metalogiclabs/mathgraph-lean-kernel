#!/usr/bin/env python3
"""Lean Refactor Arena proof-length metric.

This reproduces the tokenization used by the public reference implementation.
For live benchmark rows, the frozen statement gives us an even safer boundary:
the proof is everything after the statement's top-level assignment delimiter.

The implementation is regression-tested by requiring all live reference proofs
to reproduce their published proof_length exactly.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from official_jsonl import load

LEAN_OPERATORS = [
    ":=", "!=", "&&", "-.", "->", "←", "..", "...", "::", ":>",
    "<;>", ";;", "==", "||", "=>", "<=", ">=", "⁻¹", "?_",
]
LEAN_OPERATORS_SPACED = [" ".join(conn) for conn in LEAN_OPERATORS]
LEAN_OPERATORS_DICT = dict(zip(LEAN_OPERATORS_SPACED, LEAN_OPERATORS, strict=False))


def remove_comments_reference(text: str) -> str:
    # Match the public reference implementation rather than the stricter
    # security scanner used by arena_upload.py.
    text = re.sub(r"/-.*?-/", "", text, flags=re.DOTALL)
    cleaned_lines = []
    for line in text.split("\n"):
        cleaned_line = line.split("--", 1)[0]
        if cleaned_line.strip() == "":
            continue
        cleaned_lines.append(cleaned_line)
    return "\n".join(cleaned_lines).strip()


def lexer_count(lean_snippet: str) -> int:
    count = 0
    for line in lean_snippet.splitlines():
        tokens: list[str] = []
        token = ""
        for ch in line:
            if ch == " ":
                if token:
                    tokens.append(token)
                    token = ""
            elif ch.isalnum() or ch in "._'":
                token += ch
            else:
                if token:
                    tokens.append(token)
                    token = ""
                tokens.append(ch)
        if token:
            tokens.append(token)
        tokenized_line = " ".join(tokens)
        for conn in LEAN_OPERATORS_SPACED:
            if conn in tokenized_line:
                tokenized_line = tokenized_line.replace(
                    conn, LEAN_OPERATORS_DICT[conn]
                )
        count += len(tokenized_line.split(" "))
    return count


def proof_length_live(statement: str, full_declaration: str) -> int:
    code = remove_comments_reference(full_declaration)
    stmt = remove_comments_reference(statement)
    if not code.startswith(stmt):
        raise ValueError("candidate does not begin with frozen statement")
    tail = code[len(stmt):].lstrip()
    if not tail.startswith(":="):
        raise ValueError("candidate has no proof assignment after frozen statement")
    proof = tail[2:]
    return lexer_count(proof)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("regression")
    r.add_argument("--benchmark", required=True)

    c = sub.add_parser("count")
    c.add_argument("--benchmark", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--proof-file", required=True)

    args = ap.parse_args()
    rows = load(Path(args.benchmark))

    if args.cmd == "regression":
        failures = []
        for row in rows:
            got = proof_length_live(row["statement"], row["src"])
            expected = int(row["proof_length"])
            if got != expected:
                failures.append((row["name"], expected, got))
        if failures:
            raise SystemExit(f"proof-length regression mismatch: {failures}")
        print(f"VERIFIED_OFFICIAL_PROOF_LENGTH_REGRESSION count={len(rows)}")
        return 0

    matches = [row for row in rows if row["name"] == args.name]
    if len(matches) != 1:
        raise SystemExit(f"expected one row named {args.name!r}")
    proof = Path(args.proof_file).read_text(encoding="utf-8")
    n = proof_length_live(matches[0]["statement"], proof)
    print(json.dumps({"name": args.name, "proof_length": n}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
