#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from msikernel.trace import TraceRow, compile_anonymous_trace_interface

PREFIX = "MSI_TRACE|"


def load(path: Path):
    vectors = []
    for line in path.read_text(errors="replace").splitlines():
        if not line.startswith(PREFIX):
            continue
        parts = line.split("|")
        if len(parts) != 4:
            raise SystemExit(f"malformed trace row: {line!r}")
        state, c0, c1 = parts[1:]
        vectors.append((state, c0, c1))
    if not vectors:
        raise SystemExit("no MSI_TRACE rows found")
    return vectors


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: compile_real_msi_trace.py CORPUS TRACE OUT_JSON")
    corpus, trace_path, out_path = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    vectors = load(trace_path)

    rows = []
    for state, c0, c1 in vectors:
        rows.append(TraceRow(state=state, context="0", outcome=c0))
        rows.append(TraceRow(state=state, context="1", outcome=c1))

    interface, coverage = compile_anonymous_trace_interface(
        f"real-{corpus}", rows, context_order=("0", "1")
    )
    classes = interface.equivalence.num_classes()
    signatures = Counter((c0, c1) for _, c0, c1 in vectors)
    n = len(vectors)

    # Relabel all nonzero c0 outcomes and swap the binary c1 labels.  The
    # quotient cardinality must be invariant because outcome names are not
    # ontological in MSI; only equality fibers matter.
    c0_values = sorted({c0 for _, c0, _ in vectors if c0 != "0"})
    relabel = {v: f"r{i}" for i, v in enumerate(reversed(c0_values), 1)}
    rows2 = []
    for state, c0, c1 in vectors:
        rows2.append(TraceRow(state=state, context="x", outcome="z" if c0 == "0" else relabel[c0]))
        rows2.append(TraceRow(state=state, context="y", outcome="a" if c1 == "1" else "b"))
    interface2, coverage2 = compile_anonymous_trace_interface(
        f"real-{corpus}-relabel", rows2, context_order=("x", "y")
    )
    if interface2.equivalence.num_classes() != classes:
        raise SystemExit("outcome relabeling changed quotient cardinality")

    result = {
        "corpus": corpus,
        "events": n,
        "required_cells": coverage.required_cells,
        "observed_cells": coverage.observed_cells,
        "complete": coverage.complete,
        "classes": classes,
        "compression": n / classes,
        "largest_class": max(signatures.values()),
        "nonzero_c0_outcomes": len(c0_values),
        "c1_positive": sum(1 for _, _, c1 in vectors if c1 == "1"),
        "outcome_relabel_invariant": coverage2.complete and interface2.equivalence.num_classes() == classes,
        "signature_histogram": [
            {"outcome0": a, "outcome1": b, "count": count}
            for (a, b), count in signatures.most_common()
        ],
    }
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"{corpus.upper()}_TRACE_EVENTS={n}")
    print(f"{corpus.upper()}_TRACE_CELLS={coverage.observed_cells}/{coverage.required_cells}")
    print(f"{corpus.upper()}_TRACE_COMPLETE={'PASS' if coverage.complete else 'FAIL'}")
    print(f"{corpus.upper()}_INDUCED_CLASSES={classes}")
    print(f"{corpus.upper()}_QUOTIENT_COMPRESSION={n / classes:.3f}")
    print(f"{corpus.upper()}_OUTCOME_RELABEL_INVARIANT={'PASS' if result['outcome_relabel_invariant'] else 'FAIL'}")


if __name__ == "__main__":
    main()
