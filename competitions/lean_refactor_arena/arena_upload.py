#!/usr/bin/env python3
"""Build and preflight the actual Lean Refactor Arena upload JSONL.

The public Space accepts rows containing:
  {"name": "<benchmark theorem>", "proof": "<full Lean declaration>"}

Fail-closed properties:
- every warm-up problem is emitted exactly once by default;
- absent candidates fall back to the frozen reference proof;
- the frozen theorem statement must remain the normalized prefix;
- the Space's current forbidden-pattern and size policy is mirrored locally;
- output is capped at the Space's current 8 MiB intake limit.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from official_jsonl import load

MAX_PROOF_BYTES = 256 * 1024
MAX_SUBMISSION_BYTES = 8 * 1024 * 1024

FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("#eval", re.compile(r"#\s*eval\b")),
    ("#reduce", re.compile(r"#\s*reduce\b")),
    ("IO.", re.compile(r"\bIO\.")),
    ("unsafe def/fun/theorem", re.compile(r"\bunsafe\s+(def|fun|theorem|lemma)\b")),
    ("extern", re.compile(r"\bextern\b")),
    ("initialize", re.compile(r"\binitialize\b")),
    ("@[implemented_by]", re.compile(r"@\[\s*implemented[_]?[Bb]y\b")),
    ("@[extern]", re.compile(r"@\[\s*extern\b")),
    ("sorry", re.compile(r"\bsorry\b")),
    ("sorryAx", re.compile(r"\bsorryAx\b")),
    ("admit", re.compile(r"\badmit\b")),
    ("axiom", re.compile(r"\baxiom\b")),
    ("native_decide", re.compile(r"\bnative_decide\b")),
    ("ofReduceBool", re.compile(r"\bofReduceBool\b")),
    ("ofReduceNat", re.compile(r"\bofReduceNat\b")),
    ("run_cmd", re.compile(r"\brun_cmd\b")),
    ("run_elab", re.compile(r"\brun_elab\b")),
    ("#exit", re.compile(r"#\s*exit\b")),
    ("#count_heartbeats", re.compile(r"#\s*count_heartbeats\b")),
    ("attribute command", re.compile(r"(?m)^\s*attribute\b")),
    (
        "macro/elab/notation",
        re.compile(r"\b(macro|macro_rules|elab|elab_rules|notation|syntax)\b"),
    ),
    ("deriving instance", re.compile(r"\bderiving\s+instance\b")),
    (
        "auxiliary declaration",
        re.compile(r"(?m)^\s*(def|abbrev|instance|structure|inductive|class|opaque)\b"),
    ),
]


def strip_lean_comments(text: str) -> str:
    """Mirror the public Space's string-aware nested Lean-comment scanner."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            out.append(c)
            i += 1
            while i < n:
                out.append(text[i])
                if text[i] == "\\" and i + 1 < n:
                    out.append(text[i + 1])
                    i += 2
                    continue
                if text[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        if text.startswith("/-", i):
            depth, i = 1, i + 2
            while i < n and depth:
                if text.startswith("/-", i):
                    depth += 1
                    i += 2
                elif text.startswith("-/", i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            out.append(" ")
            continue
        if text.startswith("--", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def normalize_ws(text: str) -> str:
    return " ".join(text.split())


def statement_integrity(statement: str, candidate: str) -> bool:
    # Do not split on the first proof delimiter: valid benchmark statements
    # themselves contain local let-bindings using :=.
    s = normalize_ws(strip_lean_comments(statement))
    c = normalize_ws(strip_lean_comments(candidate))
    return c.startswith(s + " :=")


def forbidden_reason(proof: str) -> str | None:
    if len(proof.encode("utf-8")) > MAX_PROOF_BYTES:
        return f"too large (> {MAX_PROOF_BYTES // 1024} KB)"
    stripped = strip_lean_comments(proof)
    for label, pat in FORBIDDEN_PATTERNS:
        if pat.search(stripped):
            return label
    return None


def read_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line_no, raw in enumerate(f, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: bad JSON: {exc}")
            rows.append(row)
    return rows


def candidate_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    out: dict[str, str] = {}
    for line_no, row in enumerate(read_rows(path), 1):
        name = str(row.get("name") or "")
        proof = str(row.get("proof") or "")
        if not name or not proof:
            raise SystemExit(f"{path}:{line_no}: candidate row needs name and proof")
        if name in out:
            raise SystemExit(f"{path}:{line_no}: duplicate candidate name {name}")
        out[name] = proof
    return out


def preflight(benchmark: list[dict], upload: list[dict], require_full: bool = True) -> dict:
    bench = {r["name"]: r for r in benchmark}
    seen: set[str] = set()
    problems: list[str] = []

    for i, row in enumerate(upload, 1):
        name = str(row.get("name") or "")
        proof = str(row.get("proof") or "")
        if not name or not proof:
            problems.append(f"row {i}: needs name and proof")
            continue
        if name in seen:
            problems.append(f"row {i}: duplicate benchmark name {name}")
            continue
        seen.add(name)
        frozen = bench.get(name)
        if frozen is None:
            problems.append(f"row {i}: unknown benchmark theorem {name}")
            continue
        bad = forbidden_reason(proof)
        if bad:
            problems.append(f"{name}: forbidden pattern {bad}")
        if not statement_integrity(str(frozen["statement"]), proof):
            problems.append(f"{name}: frozen theorem statement changed")

    missing = [r["name"] for r in benchmark if r["name"] not in seen]
    if require_full and missing:
        problems.append(f"missing {len(missing)} benchmark theorem(s): {missing}")

    return {
        "ok": not problems,
        "rows": len(upload),
        "benchmark_count": len(benchmark),
        "covered": len(seen & set(bench)),
        "missing": missing,
        "problems": problems,
    }


def build(benchmark_path: Path, candidates_path: Path | None, out_path: Path) -> dict:
    benchmark = load(benchmark_path)
    candidates = candidate_map(candidates_path)
    bench_names = {r["name"] for r in benchmark}
    unknown = sorted(set(candidates) - bench_names)
    if unknown:
        raise SystemExit(f"candidate artifact contains unknown theorem names: {unknown}")

    rows: list[dict] = []
    used_candidates = 0
    for frozen in benchmark:
        name = frozen["name"]
        proof = candidates.get(name, frozen["src"])
        if name in candidates:
            used_candidates += 1
        rows.append({"name": name, "proof": proof})

    report = preflight(benchmark, rows, require_full=True)
    if not report["ok"]:
        raise SystemExit("Arena preflight refused upload:\n- " + "\n- ".join(report["problems"]))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    size = out_path.stat().st_size
    if size > MAX_SUBMISSION_BYTES:
        out_path.unlink(missing_ok=True)
        raise SystemExit(
            f"Arena upload exceeds {MAX_SUBMISSION_BYTES // (1024*1024)} MiB: {size} bytes"
        )

    report.update(
        {
            "schema": "mathgraph.lean-refactor-arena.upload-preflight.v1",
            "output": str(out_path),
            "bytes": size,
            "candidate_overrides": used_candidates,
            "fallback_references": len(rows) - used_candidates,
        }
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    print("VERIFIED_FULL_COVERAGE_ARENA_UPLOAD")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--benchmark", required=True)
    b.add_argument("--candidates")
    b.add_argument("--out", required=True)
    b.add_argument("--report")

    v = sub.add_parser("validate")
    v.add_argument("--benchmark", required=True)
    v.add_argument("--upload", required=True)
    v.add_argument("--allow-sparse", action="store_true")

    args = ap.parse_args()
    benchmark_path = Path(args.benchmark)

    if args.cmd == "build":
        report = build(
            benchmark_path,
            Path(args.candidates) if args.candidates else None,
            Path(args.out),
        )
        if args.report:
            Path(args.report).write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return 0

    benchmark = load(benchmark_path)
    upload = read_rows(Path(args.upload))
    report = preflight(benchmark, upload, require_full=not args.allow_sparse)
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["ok"]:
        raise SystemExit("Arena upload preflight failed")
    print("VERIFIED_ARENA_UPLOAD_PREFLIGHT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
