#!/usr/bin/env python3
"""Fail-closed evaluator for Lean Refactor Arena candidates.

The evaluator deliberately separates:
  * statement integrity
  * Lean acceptance
  * local source-size proxy
  * measured wall time

Official Arena scoring remains authoritative.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_']*|[0-9]+|:=|=>|->|<-|<=|>=|==|!=|&&|\|\||"
    r"[^\s]",
    re.UNICODE,
)


def strip_comments(src: str) -> str:
    # Sufficient for the integrity gate: remove line comments and non-nested blocks.
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"--[^\n]*", " ", src)
    return src


def declaration_head(src: str) -> str:
    clean = strip_comments(src)
    match = re.search(r"\b(theorem|lemma)\b", clean)
    if not match:
        raise ValueError("no theorem/lemma declaration found")
    tail = clean[match.start():]
    # Competition fixtures use declaration := by/proof. Keep only the statement.
    cut = tail.find(":=")
    if cut < 0:
        raise ValueError("declaration has no ':=' delimiter")
    return " ".join(tail[:cut].split())


def token_count(src: str) -> int:
    return len(TOKEN_RE.findall(strip_comments(src)))


def run_lean(path: Path, lean: str, timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(
        [lean, str(path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    elapsed = time.perf_counter() - started
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "wall_seconds": elapsed,
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-8000:],
    }


def evaluate_case(root: Path, case: dict[str, Any], lean: str) -> dict[str, Any]:
    case_id = case["id"]
    reference_path = root / case["reference"]
    candidate_path = root / case["candidate"]
    timeout = int(case.get("timeout_seconds", 60))

    reference_src = reference_path.read_text(encoding="utf-8")
    candidate_src = candidate_path.read_text(encoding="utf-8")

    ref_head = declaration_head(reference_src)
    cand_head = declaration_head(candidate_src)
    statement_same = ref_head == cand_head

    ref_run = run_lean(reference_path, lean, timeout)
    cand_run = run_lean(candidate_path, lean, timeout) if statement_same else {
        "ok": False,
        "returncode": None,
        "wall_seconds": None,
        "stdout": "",
        "stderr": "statement-integrity gate failed",
    }

    ref_tokens = token_count(reference_src)
    cand_tokens = token_count(candidate_src)
    valid = bool(statement_same and ref_run["ok"] and cand_run["ok"])

    token_reduction = (ref_tokens - cand_tokens) / ref_tokens if ref_tokens else 0.0
    wall_reduction = None
    if valid and ref_run["wall_seconds"] and cand_run["wall_seconds"] is not None:
        wall_reduction = (
            ref_run["wall_seconds"] - cand_run["wall_seconds"]
        ) / ref_run["wall_seconds"]

    return {
        "id": case_id,
        "valid": valid,
        "statement_same": statement_same,
        "reference": {
            "path": str(reference_path),
            "tokens_proxy": ref_tokens,
            "lean": ref_run,
        },
        "candidate": {
            "path": str(candidate_path),
            "tokens_proxy": cand_tokens,
            "lean": cand_run,
        },
        "improvement": {
            "token_reduction_fraction": token_reduction if valid else None,
            "wall_reduction_fraction": wall_reduction,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    results = [evaluate_case(root, case, args.lean) for case in manifest["cases"]]
    report = {
        "schema": "mathgraph.lean-refactor-arena.eval.v1",
        "all_valid": all(r["valid"] for r in results),
        "cases": results,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["all_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
