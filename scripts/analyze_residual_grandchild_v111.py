#!/usr/bin/env python3
import itertools
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

EVENT_RE = re.compile(
    r"V111_EVENT fr=(\d+) ar=(\d+) fm=(\d+) am=(\d+) "
    r"ffr=(\d+) far=(\d+) ffm=(\d+) fam=(\d+) "
    r"afr=(\d+) aar=(\d+) afm=(\d+) aam=(\d+) admit=(\d+)"
)

BASE = ("fr", "ar", "fm", "am")
EXT = ("ffr", "far", "ffm", "fam", "afr", "aar", "afm", "aam")

def load(out_dir):
    rows = []
    for path in sorted(Path(out_dir).glob("*.stderr")):
        workload = path.stem
        for line in path.read_text(errors="replace").splitlines():
            m = EVENT_RE.search(line)
            if not m:
                continue
            vals = list(map(int, m.groups()))
            row = dict(zip(BASE + EXT + ("admit",), vals))
            row["workload"] = workload
            rows.append(row)
    return rows

def grouped(rows, features):
    d = defaultdict(lambda: [0, 0, set()])
    for r in rows:
        k = tuple(r[f] for f in features)
        d[k][r["admit"]] += 1
        d[k][2].add(r["workload"])
    return d

def score(rows, features):
    g = grouped(rows, features)
    mixed = {k:v for k,v in g.items() if v[0] and v[1]}
    errors = sum(min(v[0], v[1]) for v in g.values())
    return {
        "features": list(features),
        "cost": len(features),
        "cells": len(g),
        "mixed_cells": len(mixed),
        "errors": errors,
        "pure": not mixed,
        "mixed_mass": sum(v[0]+v[1] for v in mixed.values()),
    }, mixed

def best_for_cell(rows):
    candidates = []
    for n in range(len(EXT)+1):
        for subset in itertools.combinations(EXT, n):
            s, _ = score(rows, subset)
            candidates.append(s)
    pure = [x for x in candidates if x["pure"]]
    if pure:
        best = min(pure, key=lambda x:(x["cost"], x["cells"], x["features"]))
    else:
        best = min(candidates, key=lambda x:(x["errors"], x["cost"], x["mixed_mass"], x["features"]))
    return best, candidates

def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: analyze_residual_grandchild_v111.py OUT_DIR REPORT_DIR")
    out_dir, report_dir = map(Path, sys.argv[1:])
    report_dir.mkdir(parents=True, exist_ok=True)
    rows = load(out_dir)
    if not rows:
        raise SystemExit("V111: no residual events")

    by_base = defaultdict(list)
    for r in rows:
        by_base[tuple(r[x] for x in BASE)].append(r)

    cell_reports = []
    all_pure = True
    for base, cell_rows in sorted(by_base.items()):
        best, candidates = best_for_cell(cell_rows)
        full, mixed = score(cell_rows, EXT)
        all_pure &= best["pure"]
        residual = []
        for k, v in sorted(mixed.items()):
            residual.append({
                **dict(zip(EXT, k)),
                "abort": v[0],
                "admit": v[1],
                "workloads": sorted(v[2]),
                "mass": v[0] + v[1],
            })
        report = {
            "base": dict(zip(BASE, base)),
            "events": len(cell_rows),
            "best": best,
            "full": full,
            "residual": residual,
            "candidates": candidates,
        }
        cell_reports.append(report)
        print("V111_CELL base=" + ",".join(f"{k}={v}" for k,v in zip(BASE,base)))
        print("V111_EVENTS=" + str(len(cell_rows)))
        print("V111_BEST_FEATURES=" + ",".join(best["features"]))
        print("V111_BEST_COST=" + str(best["cost"]))
        print("V111_BEST_PURE=" + str(best["pure"]).upper())
        print("V111_BEST_ERRORS=" + str(best["errors"]))
        print("V111_FULL_MIXED_CELLS=" + str(full["mixed_cells"]))
        print("V111_FULL_MIXED_MASS=" + str(full["mixed_mass"]))
        for item in residual[:25]:
            print("V111_RESIDUAL " + " ".join(f"{f}={item[f]}" for f in EXT)
                  + f" admit={item['admit']} abort={item['abort']} mass={item['mass']}")
        if len(residual) > 25:
            print(f"V111_RESIDUAL_TRUNCATED={len(residual)-25}")

    decision = "COMPILE" if all_pure else "REFINE"
    final = {
        "authority": {
            "base_language": list(BASE),
            "authorized_extension_language": list(EXT),
            "extension_cost": "unit cost per immediate grandchild root/mask field",
            "selection": "per V110 residual cell, minimum-cardinality exact separator; otherwise minimum empirical error",
        },
        "events": len(rows),
        "workloads": sorted({r["workload"] for r in rows}),
        "decision": decision,
        "cells": cell_reports,
    }
    (report_dir / "v111_report.json").write_text(json.dumps(final, indent=2, sort_keys=True))
    print(f"V111_DECISION={decision}")
    print(f"V111_TOTAL_EVENTS={len(rows)}")
    print("V111_COMPLETE=PASS")

if __name__ == "__main__":
    main()
