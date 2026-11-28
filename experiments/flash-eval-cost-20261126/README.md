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
Native prefix runs are observations, not full-input performance claims.

## Completed full-input result

[Run 45801716738](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45801716738)
accepts all 739,167 original declarations with two checking workers. Independent
verification rehashes the archive, checks CRC, reconstructs all 14,418 raw census
records and verifies the observation source tree, executable, tests and source
controls. `whole-native/` retains the result, verification, compressed raw census
records and the digest of every original archive member. `verify_census.py`
rechecks the downloaded archive; the full input is hashed on the hosted runner.

| Event | Complete-input count |
| --- | ---: |
| Open-expression evaluation cache hits | 312,364,520 |
| Open-expression evaluation cache misses | 311,068,218 |
| All environment-pruning calls | 835,459,054 |
| Cold pruning calls | 209,024,158 |
| Cold pruning returning an existing final frame | 89,651,864 |

These are event counts from an instrumented native build, not instruction-cost
shares or evidence that removing an event improves performance. The unmodified
source remains the qualified release, at 87.411 official virtual seconds.

The completed scheduling-batch trial at run 45737482656 saved 0.836% full-input
software instructions, below its declared 1% priority gate. Inlining at run
45730741082 raised median native CPU by 2.750%; neither is promoted here.

The first isolated hypothesis was a paged exact-key front cache for evaluation:
an expression-indexed recent result can avoid canonicalizing its environment
and probing the general cache on an exact original-environment hit. Keys retain
the complete expression identity, original environment identity and cache
generation. Namespace and session resets must invalidate it. Earlier bounded
hash-table aliases on the old core were negative results; this representation
required its own measurement. It raises prefix software instructions by 9.143%
in two alternating pairs and is REJECTED for performance promotion. A second
prototype relying on existing interning for open Lambda/Pi values raises them
by 0.831% and is also REJECTED. Both pass their library/source-control gates;
neither enters broad or whole-input qualification after its failed cost gate.
Their original patches, exact inputs/executables, controls and raw comparison
receipts are retained in the adjacent trial directories.

The cache-overhead hypothesis has not produced a faster checker. The residual
is reducing actual evaluation work or representation cost enough to remove
about 130 billion retired instructions on full Mathlib. Event counts alone do
not identify that saving. No new Arena submission follows from these trials.
