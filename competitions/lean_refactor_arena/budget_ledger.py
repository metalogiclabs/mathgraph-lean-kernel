#!/usr/bin/env python3
"""Append-only Track-1 spend ledger with a hard fail-closed per-problem cap."""

from __future__ import annotations
import argparse, json, os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

CAP = Decimal("3.00")

def read_total(path: Path, problem: str) -> Decimal:
    total = Decimal("0")
    if not path.exists():
        return total
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        row = json.loads(raw)
        if row.get("problem") == problem:
            total += Decimal(str(row["usd"]))
    return total

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--problem", required=True)
    ap.add_argument("--usd", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--purpose", required=True)
    args = ap.parse_args()

    ledger = Path(args.ledger)
    charge = Decimal(args.usd)
    if charge < 0:
        raise SystemExit("negative charge refused")
    previous = read_total(ledger, args.problem)
    after = previous + charge
    if after > CAP:
        raise SystemExit(
            f"TRACK1_BUDGET_REFUSED problem={args.problem} "
            f"previous_usd={previous} attempted_usd={charge} after_usd={after} cap_usd={CAP}"
        )

    row = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "problem": args.problem,
        "usd": str(charge),
        "model": args.model,
        "purpose": args.purpose,
        "cumulative_usd": str(after),
    }
    ledger.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(ledger, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
    print(f"TRACK1_BUDGET_OK problem={args.problem} cumulative_usd={after} cap_usd={CAP}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
