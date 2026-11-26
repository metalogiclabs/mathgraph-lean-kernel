# Full Mathlib result: separate candidate

[Run 45723515088](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45723515088)
completed on harness eb070281e4a06e2d729d7d5cabd2185ec7ea6c37.
Artifact 15073369717 has SHA-256
`6f55b2f7d754e4310589fe74aed040ae98ba82d39ba395bffd7cb6d439a0821e`.
The exact original ZIP is retained as `full-result.zip`; the adjacent
`verify_full_artifact.py` independently reconciles its retained evidence.

| Matched full Mathlib result | Qualified core | Inlining candidate |
| --- | ---: | ---: |
| Software instructions, pair 1 | 545,995,778,729 | 539,569,091,699 |
| Software instructions, pair 2 | 545,996,230,546 | 539,569,929,763 |
| Native CPU median, seconds | 152.630 | 153.495 |
| Maximum observed peak RSS, KiB | 4,865,640 | 4,911,108 |

The geometric instruction ratio is **0.988229778511139**, a **1.1770% reduction**.
Both pairs pass the predeclared ratio <=0.99 gate. CPU rose **0.5667%** and
observed peak RSS rose **0.9345%**, within the declared <=5% and <=10% regression
limits. These observations establish no native CPU improvement. The count
reduction must not be converted to an Arena time or multiplied into a public score.

Every one of eight full executions accepted the unchanged 6,326,141,213-byte
input with exactly 739,167 declarations. SHA-256:
`f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec`.
Native runs used two checking workers, diagnostic runs one. The software client
counts application basic-block instructions including libraries; it is not the
Arena hardware event. Generic build flags disable AVX-family features, while
the Arena descriptor uses `target-cpu=native`.

Both binaries were frozen before Cargo tests and checked again after all runs.
The candidate SHA-256 is
`a76e2bbfe07ce80b204937548b7a00524bee1bff113fe19c9e1244ed93443f46`.
The baseline is the already profiled frozen `09fe7ecf…`; compiler identity and
build flags match. Source tree `de6696fcecbe99e6fcab5bb68c5974e1e9a04e49`
is exactly bc704eeb plus the one `#[inline(always)]` attribute on `eval_node`.
No checking rule, binding/universe context, input, verdict or resource limit changed.

The frozen candidate also matched **230/230 portable prescribed outcomes** and
**16/16 source-metadata controls**. The source suite passed 39 library tests
and two integration tests; its optional empty-corpus integration test is not a
corpus qualification. The three exact calibration loops and every complete
block-table sum match. Shared-code-cache mode is rejected by the client.
The retained 32-bit SDK warnings do not establish a failed 64-bit execution;
the raw warnings and SDK/preparer/client identities are preserved explicitly.

**Decision:** the declared full-Mathlib instruction gate is WARRANTED within
this boundary. The source remains a separate **CANDIDATE**, excluded from Arena
PR #398. The nine other generic large inputs were still UNKNOWN at that point.
The follow-up below closes that residual and records a native CPU regression;
the Arena hardware result remains UNKNOWN. The qualified submitted core remains bc704eeb with its
separate 240-input source qualification. Historical local SIGKILLs and the first
invalidated mutable-executable run remain preserved; this new isolated CI result
does not retroactively turn those observations into successful executions.


## Follow-up: generic 240 complete; native CPU promotion rejected

[Run 45730741082](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45730741082)
passed all nine remaining large inputs using the exact frozen a76e2b executable,
unchanged prescribed hashes and original timeout budgets. The independently
verified join now establishes **240/240 prescribed outcomes for this generic
executable**, including the complete Navier–Stokes–Euler input.

The separately built native candidate passed 230 portable outcomes, 16 identical
source controls and all six full-Mathlib executions. It was slower in every
alternating pair: CPU ratios 1.009300, 1.022483 and 1.027501; median CPU
127.63 seconds for the baseline versus 131.14 for the candidate (**+2.7501%**).
The predeclared native CPU promotion gate failed.

[Committed outcome and independent raw evidence](https://github.com/metalogiclabs/mathgraph-lean-kernel/tree/a84b549e317e13e44d6b90dfe42700091a9e06f0/experiments/flash-inline-native-large-20261126)
preserve the positive generic compatibility result and the negative native CPU
result separately. This supersedes the pending-nine-generic-input status above.
The candidate remains excluded from PR #398; hardware instruction ordering and
the native executable's other nine large inputs remain UNKNOWN.
