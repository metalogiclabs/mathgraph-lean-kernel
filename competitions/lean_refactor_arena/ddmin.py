#!/usr/bin/env python3
"""Verifier-guided proof contraction by deletion only.

No Lean tactic or lemma is supplied by this search. It may only delete tokens
already present in the reference proof. Lean decides which contractions survive.
"""

from __future__ import annotations
import argparse, json, re, subprocess, tempfile
from pathlib import Path

TOKEN = re.compile(
    r"<;>|:=|=>|->|←|\.\.\.|\.\.|::|:>|==|!=|&&|\|\||<=|>=|⁻¹|\?_"
    r"|[A-Za-z_][A-Za-z0-9_']*|[0-9]+|[^\s]"
)

def split_declaration(src: str) -> tuple[str, list[str]]:
    i = src.find(":=")
    if i < 0:
        raise ValueError("expected ':=' declaration delimiter")
    signature = src[:i].rstrip()
    proof = src[i + 2:]
    return signature, TOKEN.findall(proof)

def render(signature: str, proof_tokens: list[str]) -> str:
    return signature + " := " + " ".join(proof_tokens) + "\n"

def verifies(src: str, lean: str, timeout: int) -> tuple[bool, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".lean", encoding="utf-8", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        p = subprocess.run(
            [lean, path],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return p.returncode == 0, (p.stdout + p.stderr)[-4000:]
    finally:
        Path(path).unlink(missing_ok=True)

def ddmin(signature: str, tokens: list[str], lean: str, timeout: int, max_checks: int):
    checks = 0
    current = tokens[:]
    trace = []
    n = 2
    while len(current) >= 2 and checks < max_checks:
        chunk = max(1, (len(current) + n - 1) // n)
        accepted = False
        for start in range(0, len(current), chunk):
            if checks >= max_checks:
                break
            candidate = current[:start] + current[start + chunk:]
            if not candidate:
                continue
            checks += 1
            ok, detail = verifies(render(signature, candidate), lean, timeout)
            trace.append({
                "check": checks,
                "before_tokens": len(current),
                "after_tokens": len(candidate),
                "deleted_start": start,
                "deleted_count": min(chunk, len(current) - start),
                "accepted": ok,
                "detail": detail if not ok else "",
            })
            if ok:
                current = candidate
                n = max(2, n - 1)
                accepted = True
                break
        if not accepted:
            if n >= len(current):
                break
            n = min(len(current), n * 2)
    return current, checks, trace

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--trace", required=True)
    ap.add_argument("--lean", default="lean")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--max-checks", type=int, default=200)
    args = ap.parse_args()

    src = Path(args.input).read_text(encoding="utf-8")
    signature, tokens = split_declaration(src)
    ok, detail = verifies(render(signature, tokens), args.lean, args.timeout)
    if not ok:
        raise SystemExit("reference proof does not verify:\n" + detail)

    final, checks, trace = ddmin(signature, tokens, args.lean, args.timeout, args.max_checks)
    out_src = render(signature, final)
    ok, detail = verifies(out_src, args.lean, args.timeout)
    if not ok:
        raise SystemExit("internal error: retained final proof failed replay:\n" + detail)

    Path(args.output).write_text(out_src, encoding="utf-8")
    report = {
        "schema": "mathgraph.lean-refactor-arena.ddmin.v1",
        "checks": checks,
        "initial_proof_tokens": len(tokens),
        "final_proof_tokens": len(final),
        "reduction_fraction": (len(tokens) - len(final)) / len(tokens) if tokens else 0,
        "final_proof": out_src,
        "trace": trace,
    }
    Path(args.trace).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "trace"}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
