#!/usr/bin/env python3
"""Probe structural proof candidates in an exact Lean project.

This is the first lawful expansion after deletion-only search reaches a
certified residual.  Candidate generation is external to this verifier; this
program only binds candidates to the frozen theorem statement, compiles them in
the pinned project, measures the organizer proof-length metric, and preserves
all failures.

The result is evidence, not a submission.  A candidate is promoted only if Lean
accepts it and it strictly improves the frozen reference proof length.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import uuid
from pathlib import Path

from arena_metrics import proof_length_live
from official_jsonl import load, relative_path

FORBIDDEN = re.compile(
    r"\b(?:sorry|sorryAx|admit|axiom|native_decide|run_cmd|run_elab)\b"
    r"|#\s*(?:eval|reduce|exit|count_heartbeats)\b"
    r"|\bIO\."
)


def choose_row(rows: list[dict], name: str) -> dict:
    xs = [r for r in rows if r["name"] == name]
    if len(xs) != 1:
        raise SystemExit(f"expected exactly one benchmark row named {name!r}, got {len(xs)}")
    return xs[0]


def read_candidates(path: Path, name: str) -> list[dict]:
    rows = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_no}: malformed JSON: {exc}")
        if row.get("name") != name:
            continue
        label = str(row.get("label") or f"candidate-{line_no}")
        proof = str(row.get("proof") or "")
        if not proof.strip():
            raise SystemExit(f"{path}:{line_no}: empty proof for {label}")
        rows.append({"label": label, "proof": proof})
    if not rows:
        raise SystemExit(f"{path}: no candidates for {name!r}")
    return rows


class ExactWorkspace:
    def __init__(self, workspace: Path, relative: str, frozen_src: str, timeout: int):
        self.workspace = workspace.resolve()
        self.source = (self.workspace / relative).resolve()
        self.timeout = timeout
        if not self.source.is_file():
            raise SystemExit(f"source file not found: {self.source}")
        self.original = self.source.read_text(encoding="utf-8")
        count = self.original.count(frozen_src)
        if count != 1:
            raise SystemExit(f"frozen theorem occurs {count} times in source; expected 1")
        self.frozen_src = frozen_src

    def run(self, candidate: str) -> dict:
        instrumented = self.original.replace(self.frozen_src, candidate, 1)
        tmp = self.source.with_name(f"temp_lra_probe_{uuid.uuid4().hex}_{self.source.name}")
        tmp.write_text(instrumented, encoding="utf-8")
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
            return {
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
                "wall_seconds": time.perf_counter() - started,
                "stdout_tail": proc.stdout[-8000:],
                "stderr_tail": proc.stderr[-8000:],
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "ok": False,
                "timeout": True,
                "returncode": None,
                "wall_seconds": time.perf_counter() - started,
                "stdout_tail": (exc.stdout or "")[-8000:] if isinstance(exc.stdout, str) else "",
                "stderr_tail": (exc.stderr or "")[-8000:] if isinstance(exc.stderr, str) else "",
            }
        finally:
            tmp.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--out-best", required=True)
    ap.add_argument("--out-report", required=True)
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()

    rows = load(Path(args.benchmark))
    row = choose_row(rows, args.name)
    rel = relative_path(row)
    if not rel:
        raise SystemExit("exact-project structural probe requires nonblank file_path")

    reference_tokens = proof_length_live(row["statement"], row["src"])
    expected_tokens = int(row["proof_length"])
    if reference_tokens != expected_tokens:
        raise SystemExit(
            f"reference token regression mismatch: published={expected_tokens} measured={reference_tokens}"
        )

    workspace = ExactWorkspace(Path(args.workspace), rel, row["src"], args.timeout)
    baseline = workspace.run(row["src"])
    if not baseline["ok"]:
        raise SystemExit(
            "frozen reference failed exact-workspace verification:\n"
            + baseline.get("stdout_tail", "")
            + baseline.get("stderr_tail", "")
        )

    results = []
    for cand in read_candidates(Path(args.candidates), row["name"]):
        proof = cand["proof"]
        result = {
            "label": cand["label"],
            "statement_bound": False,
            "forbidden": None,
            "proof_tokens": None,
            "length_reduction_pct": None,
            "ok": False,
        }
        try:
            tokens = proof_length_live(row["statement"], proof)
            result["statement_bound"] = True
            result["proof_tokens"] = tokens
            result["length_reduction_pct"] = round(
                (reference_tokens - tokens) / reference_tokens * 100.0, 4
            )
        except ValueError as exc:
            result["error"] = str(exc)
            results.append(result)
            print(f"REJECT {cand['label']} statement-boundary {exc}", flush=True)
            continue

        hit = FORBIDDEN.search(proof)
        if hit:
            result["forbidden"] = hit.group(0)
            result["error"] = f"forbidden proof surface: {hit.group(0)}"
            results.append(result)
            print(f"REJECT {cand['label']} forbidden={hit.group(0)!r}", flush=True)
            continue

        run = workspace.run(proof)
        result.update(run)
        results.append(result)
        print(
            f"{'PASS' if run['ok'] else 'FAIL'} {cand['label']} "
            f"tokens={result['proof_tokens']} reduction={result['length_reduction_pct']}% "
            f"wall={run['wall_seconds']:.3f}s",
            flush=True,
        )

    verified = [r for r in results if r.get("ok")]
    verified.sort(key=lambda r: (int(r["proof_tokens"]), float(r["wall_seconds"]), r["label"]))
    best = verified[0] if verified else None
    best_spec = None
    if best is not None:
        best_spec = next(
            x for x in read_candidates(Path(args.candidates), row["name"])
            if x["label"] == best["label"]
        )
        Path(args.out_best).write_text(
            json.dumps({"name": row["name"], "proof": best_spec["proof"]}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    else:
        Path(args.out_best).write_text("", encoding="utf-8")

    report = {
        "schema": "mathgraph.lean-refactor-arena.structural-probe.v1",
        "name": row["name"],
        "source": row.get("source"),
        "source_path": rel,
        "workspace_commit_expected": next(iter(row["version_info"][0].values())),
        "lean_version_expected": next(iter(row["version_info"][0].keys())),
        "reference_tokens": reference_tokens,
        "reference_wall_seconds": baseline["wall_seconds"],
        "candidate_count": len(results),
        "verified_count": len(verified),
        "best_label": None if best is None else best["label"],
        "best_tokens": None if best is None else best["proof_tokens"],
        "best_length_reduction_pct": None if best is None else best["length_reduction_pct"],
        "strict_token_gain": bool(best is not None and int(best["proof_tokens"]) < reference_tokens),
        "results": results,
    }
    Path(args.out_report).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))
    if report["strict_token_gain"]:
        print("VERIFIED_STRUCTURAL_CONSEQUENCE_GAIN")
    elif verified:
        print("VERIFIED_STRUCTURAL_CANDIDATE_NO_TOKEN_GAIN")
    else:
        print("NO_VERIFIED_STRUCTURAL_CANDIDATE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
