#!/usr/bin/env python3
"""Atomic, tamper-evident Track-1 spend ledger.

Linux file locking serializes parallel workers so two model calls cannot both
observe the same remaining budget. Each admitted receipt is hash-chained.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

CAP = Decimal("3.00")
ZERO_HASH = "0" * 64


def canonical(row: dict) -> bytes:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def parse_rows(text: str) -> list[dict]:
    rows = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"ledger corruption at line {line_no}: {exc}")
    return rows


def verify_chain(rows: list[dict]) -> None:
    prev = ZERO_HASH
    for line_no, row in enumerate(rows, 1):
        claimed_prev = row.get("prev_hash")
        claimed_hash = row.get("receipt_sha256")
        if claimed_prev != prev or not claimed_hash:
            raise SystemExit(f"ledger hash-chain corruption at line {line_no}")
        payload = dict(row)
        payload.pop("receipt_sha256", None)
        actual = hashlib.sha256(canonical(payload)).hexdigest()
        if actual != claimed_hash:
            raise SystemExit(f"ledger receipt digest mismatch at line {line_no}")
        prev = claimed_hash


def total_for(rows: list[dict], problem: str) -> Decimal:
    return sum(
        (Decimal(str(row["usd"])) for row in rows if row.get("problem") == problem),
        Decimal("0"),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--problem", required=True)
    ap.add_argument("--usd", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--purpose", required=True)
    args = ap.parse_args()

    try:
        charge = Decimal(args.usd)
    except InvalidOperation:
        raise SystemExit("invalid USD charge")
    if not charge.is_finite() or charge < 0:
        raise SystemExit("non-finite or negative charge refused")

    ledger = Path(args.ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)

    # a+ plus an exclusive advisory lock makes read/check/append one atomic
    # critical section across parallel Track-1 workers on the Linux runner.
    with ledger.open("a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.seek(0)
        rows = parse_rows(f.read())
        verify_chain(rows)

        previous = total_for(rows, args.problem)
        after = previous + charge
        if after > CAP:
            raise SystemExit(
                f"TRACK1_BUDGET_REFUSED problem={args.problem} "
                f"previous_usd={previous} attempted_usd={charge} "
                f"after_usd={after} cap_usd={CAP}"
            )

        prev_hash = rows[-1]["receipt_sha256"] if rows else ZERO_HASH
        row = {
            "schema": "mathgraph.track1-spend-receipt.v2",
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "problem": args.problem,
            "usd": str(charge),
            "model": args.model,
            "purpose": args.purpose,
            "cumulative_usd": str(after),
            "prev_hash": prev_hash,
        }
        row["receipt_sha256"] = hashlib.sha256(canonical(row)).hexdigest()

        f.seek(0, os.SEEK_END)
        f.write(json.dumps(row, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    print(
        f"TRACK1_BUDGET_OK problem={args.problem} "
        f"cumulative_usd={after} cap_usd={CAP} "
        f"receipt_sha256={row['receipt_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
