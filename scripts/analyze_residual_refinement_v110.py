#!/usr/bin/env python3
import itertools
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

CELL_RE = re.compile(
    r"V109_CELL fun_root=(\S+) arg_root=(\S+) fun_mask=(\S+) arg_mask=(\S+) admit=(\d+) abort=(\d+)"
)
FEATURES = ("fun_root", "arg_root", "fun_mask", "arg_mask")

def load_cells(out_dir: Path):
    rows = []
    for path in sorted(out_dir.glob("*.stderr")):
        workload = path.stem
        for line in path.read_text(errors="replace").splitlines():
            m = CELL_RE.search(line)
            if not m:
                continue
            fr, ar, fm, am, admit, abort = m.groups()
            rows.append({
                "workload": workload,
                "fun_root": fr,
                "arg_root": ar,
                "fun_mask": fm,
                "arg_mask": am,
                "admit": int(admit),
                "abort": int(abort),
            })
    return rows

def project(rows, subset):
    cells = defaultdict(lambda: [0, 0])
    for row in rows:
        key = tuple(row[f] for f in subset)
        cells[key][0] += row["admit"]
        cells[key][1] += row["abort"]
    return cells

def stats(cells):
    total_admit = sum(v[0] for v in cells.values())
    total_abort = sum(v[1] for v in cells.values())
    mixed = {k: v for k, v in cells.items() if v[0] and v[1]}
    mixed_admit = sum(v[0] for v in mixed.values())
    mixed_abort = sum(v[1] for v in mixed.values())
    errors = sum(min(v) for v in cells.values())
    total = total_admit + total_abort
    return {
        "cells": len(cells),
        "mixed_cells": len(mixed),
        "admit": total_admit,
        "abort": total_abort,
        "mixed_admit": mixed_admit,
        "mixed_abort": mixed_abort,
        "mixed_mass": mixed_admit + mixed_abort,
        "majority_errors": errors,
        "majority_accuracy": (1.0 - errors / total) if total else 1.0,
        "pure": not mixed,
    }, mixed

def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: analyze_residual_refinement_v110.py OUT_DIR REPORT_DIR")
    out_dir = Path(sys.argv[1])
    report_dir = Path(sys.argv[2])
    report_dir.mkdir(parents=True, exist_ok=True)

    rows = load_cells(out_dir)
    if not rows:
        raise SystemExit("V110: no V109_CELL rows found")

    candidates = []
    for r in range(0, len(FEATURES) + 1):
        for subset in itertools.combinations(FEATURES, r):
            cells = project(rows, subset)
            s, mixed = stats(cells)
            candidates.append({"features": list(subset), "cost": len(subset), **s})

    candidates.sort(key=lambda x: (
        not x["pure"],
        x["cost"],
        x["majority_errors"],
        -x["majority_accuracy"],
        x["features"],
    ))
    pure = [c for c in candidates if c["pure"]]
    best = pure[0] if pure else min(
        candidates,
        key=lambda x: (x["majority_errors"], x["cost"], x["features"])
    )

    full_cells = project(rows, FEATURES)
    full_stats, full_mixed = stats(full_cells)

    residual = []
    for key, (admit, abort) in sorted(full_mixed.items()):
        residual.append({
            **dict(zip(FEATURES, key)),
            "admit": admit,
            "abort": abort,
            "mass": admit + abort,
        })

    decision = "COMPILE" if pure else "REFINE"
    report = {
        "authority": {
            "teacher": "existing sparse admission decision sparse.is_some()",
            "feature_language": list(FEATURES),
            "feature_cost": "unit cost per local field",
            "selection": "minimum-cardinality exact separator; otherwise minimum empirical error",
        },
        "rows": len(rows),
        "workloads": sorted({r["workload"] for r in rows}),
        "decision": decision,
        "best": best,
        "full_feature_stats": full_stats,
        "residual_cells": residual,
        "candidates": candidates,
    }

    (report_dir / "v110_report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    (report_dir / "v110_residual.json").write_text(json.dumps(residual, indent=2, sort_keys=True))

    print(f"V110_ROWS={len(rows)}")
    print(f"V110_WORKLOADS={len(report['workloads'])}")
    print(f"V110_DECISION={decision}")
    print(f"V110_FULL_CELLS={full_stats['cells']}")
    print(f"V110_FULL_MIXED_CELLS={full_stats['mixed_cells']}")
    print(f"V110_FULL_MIXED_MASS={full_stats['mixed_mass']}")
    print(f"V110_FULL_MAJORITY_ERRORS={full_stats['majority_errors']}")
    print(f"V110_FULL_MAJORITY_ACCURACY={full_stats['majority_accuracy']:.12f}")
    print("V110_BEST_FEATURES=" + ",".join(best["features"]))
    print(f"V110_BEST_COST={best['cost']}")
    print(f"V110_BEST_PURE={str(best['pure']).upper()}")
    print(f"V110_BEST_ERRORS={best['majority_errors']}")
    for item in residual[:50]:
        print(
            "V110_RESIDUAL "
            + " ".join(f"{f}={item[f]}" for f in FEATURES)
            + f" admit={item['admit']} abort={item['abort']} mass={item['mass']}"
        )
    if len(residual) > 50:
        print(f"V110_RESIDUAL_TRUNCATED={len(residual)-50}")
    print("V110_COMPLETE=PASS")

if __name__ == "__main__":
    main()
