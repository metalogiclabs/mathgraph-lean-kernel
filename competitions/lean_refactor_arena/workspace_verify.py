#!/usr/bin/env python3
"""Verify Arena submission records in the frozen Lean workspace.

This mirrors the organizer's core replacement semantics without depending on
their agent stack: copy the original source file beside itself, replace the
first exact occurrence of the frozen theorem source, invoke Lean through Lake,
then delete the temporary file.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import uuid
from pathlib import Path

from official_jsonl import load
from submission import read_jsonl


def resolve_source(workspace: Path, relative: str) -> Path:
    candidates = [workspace / relative]
    if not relative.endswith(".lean"):
        candidates.append(workspace / (relative + ".lean"))
    for p in candidates:
        if p.is_file():
            return p
    raise FileNotFoundError(f"workspace source not found for {relative!r}")


def verify_one(
    workspace: Path,
    frozen: dict,
    result: dict,
    timeout: int,
) -> dict:
    source_path = resolve_source(workspace, frozen["path"])
    original_file = source_path.read_text(encoding="utf-8")
    old = frozen["src"]
    new = result["proof"]

    occurrences = original_file.count(old)
    if occurrences != 1:
        return {
            "name": frozen["name"],
            "path": frozen["path"],
            "ok": False,
            "error": f"frozen theorem source occurs {occurrences} times; expected exactly 1",
        }

    replaced = original_file.replace(old, new, 1)
    tmp_name = f"temp_arena_{uuid.uuid4().hex}_{source_path.name}"
    tmp_path = source_path.with_name(tmp_name)
    tmp_path.write_text(replaced, encoding="utf-8")

    started = time.perf_counter()
    try:
        proc = subprocess.run(
            ["lake", "env", "lean", str(tmp_path.relative_to(workspace))],
            cwd=workspace,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        elapsed = time.perf_counter() - started
        return {
            "name": frozen["name"],
            "path": frozen["path"],
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "wall_seconds": elapsed,
            "stdout": proc.stdout[-12000:],
            "stderr": proc.stderr[-12000:],
            "temp_relative_path": str(tmp_path.relative_to(workspace)),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": frozen["name"],
            "path": frozen["path"],
            "ok": False,
            "timeout": True,
            "wall_seconds": time.perf_counter() - started,
            "stdout": (exc.stdout or "")[-12000:] if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "")[-12000:] if isinstance(exc.stderr, str) else "",
        }
    finally:
        tmp_path.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--input", required=True, help="organizer benchmark JSONL")
    ap.add_argument("--submission", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    workspace = Path(args.workspace).resolve()
    frozen_rows = load(Path(args.input))
    result_rows = read_jsonl(Path(args.submission))

    frozen_map = {(r["name"], r["path"]): r for r in frozen_rows}
    result_map = {(r.get("name"), r.get("path")): r for r in result_rows}
    if set(frozen_map) != set(result_map):
        raise SystemExit("submission identities differ from benchmark identities")

    keys = list(frozen_map)
    if args.limit is not None:
        keys = keys[: args.limit]

    results = []
    for key in keys:
        out = verify_one(workspace, frozen_map[key], result_map[key], args.timeout)
        results.append(out)
        verdict = "PASS" if out["ok"] else "FAIL"
        print(f"{verdict} {key[0]} {out.get('wall_seconds', 0):.3f}s", flush=True)

    report = {
        "schema": "mathgraph.lean-refactor-arena.workspace-verify.v1",
        "workspace": str(workspace),
        "verified": len(results),
        "all_valid": all(r["ok"] for r in results),
        "results": results,
    }
    Path(args.out).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not report["all_valid"]:
        raise SystemExit("one or more Arena proofs failed workspace verification")
    print(f"VERIFIED_ARENA_WORKSPACE_REPLACEMENT count={len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
