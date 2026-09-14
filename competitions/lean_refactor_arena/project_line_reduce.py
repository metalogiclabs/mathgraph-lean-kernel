#!/usr/bin/env python3
"""Verifier-guided line contraction inside an exact source workspace.

This search knows no Lean tactics or lemmas. It can only delete contiguous
lines from the existing tactic body. Every proposed deletion is tested by
replacing the frozen theorem in its original source file and invoking Lean
through the repository's Lake environment.

It is intended as the first real-benchmark acquisition baseline.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
import uuid
from pathlib import Path

from official_jsonl import load, relative_path


def choose_row(rows: list[dict], name: str) -> dict:
    matches = [r for r in rows if r["name"] == name]
    if len(matches) != 1:
        raise SystemExit(f"expected exactly one benchmark row named {name!r}, got {len(matches)}")
    return matches[0]


def split_tactic_body(row: dict) -> tuple[str, list[str]]:
    src = row["src"]
    statement = row["statement"]
    if not src.startswith(statement):
        raise SystemExit("frozen src does not begin with frozen statement")
    tail = src[len(statement):]
    marker = " := by"
    if not tail.startswith(marker):
        raise SystemExit("line reducer currently requires tactic-style ':= by' proof")
    rest = tail[len(marker):]
    if rest.startswith(" \n"):
        rest = rest[1:]
    if rest.startswith("\n"):
        rest = rest[1:]
    lines = rest.splitlines(keepends=True)
    if not lines:
        raise SystemExit("proof body has no lines")
    return statement + marker + "\n", lines


def render(prefix: str, body_lines: list[str]) -> str:
    return prefix + "".join(body_lines)


class WorkspaceVerifier:
    def __init__(self, workspace: Path, relative: str, frozen_src: str, timeout: int):
        self.workspace = workspace.resolve()
        self.source = (self.workspace / relative).resolve()
        self.frozen_src = frozen_src
        self.timeout = timeout
        if not self.source.is_file():
            raise SystemExit(f"source file not found: {self.source}")
        self.original_file = self.source.read_text(encoding="utf-8")
        count = self.original_file.count(frozen_src)
        if count != 1:
            raise SystemExit(f"frozen theorem occurs {count} times in source; expected 1")
        self.checks = 0

    def verify(self, candidate: str) -> tuple[bool, float, str]:
        self.checks += 1
        replaced = self.original_file.replace(self.frozen_src, candidate, 1)
        tmp = self.source.with_name(f"temp_lra_{uuid.uuid4().hex}_{self.source.name}")
        tmp.write_text(replaced, encoding="utf-8")
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                ["lake", "env", "lean", str(tmp.relative_to(self.workspace))],
                cwd=self.workspace,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
            )
            elapsed = time.perf_counter() - started
            detail = (proc.stdout + proc.stderr)[-8000:]
            return proc.returncode == 0, elapsed, detail
        except subprocess.TimeoutExpired as exc:
            elapsed = time.perf_counter() - started
            detail = ""
            if isinstance(exc.stdout, str):
                detail += exc.stdout
            if isinstance(exc.stderr, str):
                detail += exc.stderr
            return False, elapsed, ("TIMEOUT\n" + detail)[-8000:]
        finally:
            tmp.unlink(missing_ok=True)


def ddmin_lines(
    prefix: str,
    lines: list[str],
    verifier: WorkspaceVerifier,
    max_checks: int,
) -> tuple[list[str], list[dict]]:
    current = lines[:]
    trace: list[dict] = []
    n = 2

    while len(current) > 1 and verifier.checks < max_checks:
        chunk = max(1, math.ceil(len(current) / n))
        accepted = False
        for start in range(0, len(current), chunk):
            if verifier.checks >= max_checks:
                return current, trace
            candidate_lines = current[:start] + current[start + chunk:]
            if not candidate_lines:
                continue
            candidate = render(prefix, candidate_lines)
            ok, elapsed, detail = verifier.verify(candidate)
            event = {
                "check": verifier.checks,
                "granularity": n,
                "before_lines": len(current),
                "after_lines": len(candidate_lines),
                "deleted_start": start,
                "deleted_count": min(chunk, len(current) - start),
                "accepted": ok,
                "wall_seconds": elapsed,
                "detail": "" if ok else detail,
            }
            trace.append(event)
            print(
                f"check={verifier.checks} lines={len(current)}->{len(candidate_lines)} "
                f"delete={event['deleted_count']} accepted={ok} wall={elapsed:.3f}s",
                flush=True,
            )
            if ok:
                current = candidate_lines
                n = max(2, n - 1)
                accepted = True
                break
        if accepted:
            continue
        if n >= len(current):
            break
        n = min(len(current), n * 2)

    return current, trace


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--out-proof", required=True)
    ap.add_argument("--out-report", required=True)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--max-checks", type=int, default=80)
    args = ap.parse_args()

    rows = load(Path(args.benchmark))
    row = choose_row(rows, args.name)
    rel = relative_path(row)
    if not rel:
        raise SystemExit("project line reducer requires nonblank file_path")

    prefix, body = split_tactic_body(row)
    verifier = WorkspaceVerifier(
        Path(args.workspace),
        rel,
        row["src"],
        args.timeout,
    )

    ok, baseline_wall, detail = verifier.verify(row["src"])
    if not ok:
        raise SystemExit("frozen reference failed exact-workspace verification:\n" + detail)

    final_lines, trace = ddmin_lines(prefix, body, verifier, args.max_checks)
    final = render(prefix, final_lines)
    ok, final_wall, detail = verifier.verify(final)
    if not ok:
        raise SystemExit("retained candidate failed final replay:\n" + detail)

    out_proof = Path(args.out_proof)
    out_proof.write_text(
        json.dumps({"name": row["name"], "proof": final}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    report = {
        "schema": "mathgraph.lean-refactor-arena.project-line-reduce.v1",
        "name": row["name"],
        "source": row.get("source"),
        "workspace_commit_expected": next(iter(row["version_info"][0].values())),
        "lean_version_expected": next(iter(row["version_info"][0].keys())),
        "source_path": rel,
        "reference_reported_proof_tokens": row.get("proof_length"),
        "initial_body_lines": len(body),
        "final_body_lines": len(final_lines),
        "line_reduction_fraction": (len(body) - len(final_lines)) / len(body),
        "baseline_wall_seconds": baseline_wall,
        "final_wall_seconds": final_wall,
        "verifier_checks": verifier.checks,
        "changed": final != row["src"],
        "final_proof": final,
        "trace": trace,
    }
    Path(args.out_report).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({k: v for k, v in report.items() if k not in {"trace", "final_proof"}}, indent=2))
    if final == row["src"]:
        print("NO_VERIFIED_LINE_CONTRACTION")
    else:
        print("VERIFIED_REAL_WORKSPACE_LINE_CONTRACTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
