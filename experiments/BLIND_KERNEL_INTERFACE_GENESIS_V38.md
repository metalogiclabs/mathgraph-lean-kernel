# Blind kernel interface genesis V38

This experiment uses the prior MSI results as an actual developmental protocol rather than as a hand-selected optimization hint.

The acquisition phase exposes only the first 2,000,000 lines of the Lean Arena `std` corpus to frozen producer/consumer instrumentation. Three anonymous semantic capability classes are ranked without reading any held-out performance result. The ranking rule is fixed before evaluation: maximize independent downstream consumer fanout, then already-established redundant demand, then pre-existing ratio.

Only after the winner is frozen does the workflow materialize three checker arms from the unchanged `mathgraph` baseline: LOCAL, SHARED, and exact ABLATION. The same-source held-out slice is the next 1,000,000 `std` lines, disjoint from acquisition. The source-distinct held-out corpus is the first 1,000,000 `cedar` lines and is not executed before selection.

All three arms must produce byte-identical checker output on both held-out continuations. Deterministic Callgrind instruction counts then decide whether the selected retained interface is economically causal. The strict positive gate requires SHARED to beat both LOCAL and ABLATION on both held-out corpora. Exact ablation therefore tests whether the retained interface itself, rather than unrelated patch structure, causes the gain.

The workflow never supplies `sort`, `pi`, or `inductive` as the desired winner. Those names exist only as post-selection materializers for anonymous candidates c0/c1/c2. If the acquisition evidence selects another candidate, that materializer is used instead.

Positive decision: `BLIND_INTERFACE_GENESIS_TRANSFER`.
