# Evaluator cache census

Observation-only instrumentation of qualified source `bc704eeb`, whose official
Arena run 45787031655 accepts all 240 scored inputs and counts 524,466,904,384
Mathlib instructions (87.411150731 virtual seconds at 6 Ginstr/s).

The census preserves checker decisions and all cache keys, namespace barriers,
universe scopes and source-record checks. Private counters survive declaration
sessions and are printed when each cache is dropped. They count evaluator
entries/computations, cache hits/misses, pruning routes and reused frames.
`run_census.py` requires the original input identity, complete success marker,
raw exit zero and four exact partition identities before accepting a result.
Native one/two-worker prefix runs are observations, not full-input performance
claims. Full-input results remain UNKNOWN until the hosted receipt is verified.

The completed scheduling-batch trial at run 45737482656 saved 0.836% full-input
software instructions, below its declared 1% priority gate. Inlining at run
45730741082 raised median native CPU by 2.750%; neither is promoted here.

The next isolated hypothesis is a paged exact-key front cache for evaluation:
an expression-indexed recent result can avoid canonicalizing its environment
and probing the general cache on an exact original-environment hit. Keys retain
the complete expression identity, original environment identity and cache
generation. Namespace and session resets must invalidate it. Earlier bounded
hash-table aliases on the old core were negative results; this representation
requires its own measurement. It is not assumed to deliver the remaining 24.7%.
