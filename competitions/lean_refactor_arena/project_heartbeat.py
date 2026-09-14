#!/usr/bin/env python3
"""Measure one Arena theorem with command-scoped Lean heartbeats.

The measurement mirrors Mathlib.Util.CountHeartbeats:
- count IO.getNumHeartbeats around command elaboration;
- force Elab.async=false so theorem-body work stays inside the measurement;
- disable maxHeartbeats for the measured declaration;
- divide the internal counter by 1000 for user-facing heartbeats.

For non-Mathlib source repositories we inject a tiny measurement-only command
elaborator into a temporary sibling source file. The submitted proof itself is
never changed by this instrumentation.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import uuid
from pathlib import Path

from official_jsonl import load, relative_path
from submission import read_jsonl

HELPER = r'''
import Lean.Util.Heartbeats
import Lean.Elab.Command

open Lean Elab Command

elab "#lra_count_heartbeats " "in" ppLine cmd:command : command => do
  let start ← IO.getNumHeartbeats
  try
    elabCommand (← `(command|
      set_option Elab.async false in
      set_option maxHeartbeats 0 in
      $cmd))
  finally
    let finish ← IO.getNumHeartbeats
    let elapsed := (finish - start) / 1000
    logInfo m!"LRA_HEARTBEATS {elapsed}"
'''.lstrip()

HB_RE = re.compile(r"LRA_HEARTBEATS\s+(\d+)")


def choose(rows: list[dict], name: str) -> dict:
    xs = [r for r in rows if r["name"] == name]
    if len(xs) != 1:
        raise SystemExit(f"expected exactly one benchmark row named {name!r}")
    return xs[0]


def choose_candidate(path: Path | None, row: dict) -> str:
    if path is None:
        return row["src"]
    matches = [r for r in read_jsonl(path) if r.get("name") == row["name"]]
    if len(matches) != 1:
        raise SystemExit(
            f"candidate artifact must contain exactly one row named {row['name']!r}"
        )
    proof = str(matches[0].get("proof") or "")
    if not proof:
        raise SystemExit("candidate proof is empty")
    return proof


def insert_helper_after_imports(source: str) -> str:
    lines = source.splitlines(keepends=True)
    import_indexes = [
        i for i, line in enumerate(lines)
        if re.match(r"^\s*(?:(?:public|private|meta)\s+)*import\s+", line)
    ]
    if not import_indexes:
        raise SystemExit("source file has no import lines; cannot place measurement helper safely")
    pos = import_indexes[-1] + 1
    return "".join(lines[:pos]) + "\n" + HELPER + "\n" + "".join(lines[pos:])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--heartbeats", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--candidate")
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    benchmark = load(Path(args.benchmark))
    row = choose(benchmark, args.name)
    rel = relative_path(row)
    if not rel:
        raise SystemExit("project heartbeat mode requires nonblank file_path")

    hb_rows = read_jsonl(Path(args.heartbeats))
    hb_map = {str(r.get("name")): int(r["heartbeat"]) for r in hb_rows}
    if row["name"] not in hb_map:
        raise SystemExit(f"no reference heartbeat for {row['name']}")
    expected = hb_map[row["name"]]

    candidate = choose_candidate(Path(args.candidate) if args.candidate else None, row)
    workspace = Path(args.workspace).resolve()
    source_path = workspace / rel
    original = source_path.read_text(encoding="utf-8")
    if original.count(row["src"]) != 1:
        raise SystemExit("frozen theorem does not occur exactly once in project source")

    measured_decl = "#lra_count_heartbeats in\n" + candidate
    instrumented = original.replace(row["src"], measured_decl, 1)
    instrumented = insert_helper_after_imports(instrumented)

    tmp = source_path.with_name(f"temp_lra_hb_{uuid.uuid4().hex}_{source_path.name}")
    tmp.write_text(instrumented, encoding="utf-8")
    try:
        proc = subprocess.run(
            ["lake", "env", "lean", str(tmp.relative_to(workspace))],
            cwd=workspace,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=args.timeout,
        )
    finally:
        tmp.unlink(missing_ok=True)

    combined = proc.stdout + "\n" + proc.stderr
    matches = [int(x) for x in HB_RE.findall(combined)]
    measured = matches[-1] if matches else None
    report = {
        "schema": "mathgraph.lean-refactor-arena.project-heartbeat.v1",
        "name": row["name"],
        "source": row.get("source"),
        "path": rel,
        "ok": proc.returncode == 0 and measured is not None,
        "returncode": proc.returncode,
        "reference_heartbeat_published": expected,
        "measured_heartbeat": measured,
        "delta_from_published": None if measured is None else measured - expected,
        "ratio_to_published": None if measured is None or expected == 0 else measured / expected,
        "candidate_is_reference": candidate == row["src"],
        "stdout_tail": proc.stdout[-8000:],
        "stderr_tail": proc.stderr[-8000:],
    }
    Path(args.out).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({k: v for k, v in report.items() if not k.endswith("_tail")}, indent=2))

    if proc.returncode != 0:
        raise SystemExit("heartbeat-instrumented theorem failed to compile")
    if measured is None:
        raise SystemExit("heartbeat marker was not observed")
    print("VERIFIED_PROJECT_HEARTBEAT_MEASUREMENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
