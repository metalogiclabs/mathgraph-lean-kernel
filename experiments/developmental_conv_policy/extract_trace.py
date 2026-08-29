#!/usr/bin/env python3
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path

PREFIX = "MATHGRAPH_CONV_TRACE "


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("conv-trace.log")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("conv-trace.jsonl")
    rows = []
    for line in src.read_text(errors="replace").splitlines():
        if PREFIX not in line:
            continue
        payload = line.split(PREFIX, 1)[1].strip()
        rows.append(json.loads(payload))
    with out.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    actions = Counter(r["baseline_action"] for r in rows)
    signatures = Counter(json.dumps(r["state"], sort_keys=True) for r in rows)
    summary = {
        "records": len(rows),
        "unique_structural_states": len(signatures),
        "baseline_actions": dict(sorted(actions.items())),
        "top_states": [{"state": json.loads(s), "count": n} for s, n in signatures.most_common(20)],
    }
    Path("conv-trace-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
