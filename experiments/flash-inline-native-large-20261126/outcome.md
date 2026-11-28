# Inline candidate: qualification complete, native CPU promotion rejected

The frozen generic inline candidate now matches **240/240 prescribed outcomes**.
All nine remaining large inputs passed on their exact original bytes and original
timeout budgets. Raw declaration totals also match the qualified baseline.
The independent artifact join verified eleven ZIP SHA-256 identities and CRCs,
all prescribed names, input hashes and raw verdicts, and every retained entry digest.

- [New native and nine-large run](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45730741082)
- [Original generic qualification](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45723515088)
- [Raw evidence capsule](result.json)
- [Artifact metadata](artifact-metadata.json)
- [Independent verifier](verify_artifacts.py)

## Native comparison

Both arms used Rust 1.99.1, `target-cpu=native`, two checking workers,
and the exact 6,326,141,213-byte Mathlib export. All six executions accepted exactly
739,167 declarations. The candidate additionally matched all 230 portable outcomes
and all 16 identical source controls; its source tests passed.

| Metric | Qualified core | Inline candidate |
| --- | ---: | ---: |
| Median CPU, seconds | 127.63 | 131.14 |
| Median wall time, seconds | 69.44 | 71.19 |
| Maximum observed RSS, KiB | 4,930,096 | 4,916,040 |

Candidate-to-baseline CPU ratios were **1.009300**, **1.022483** and **1.027501**.
All three pairs were slower. The median CPU increase is **2.7501%**.
The declared native CPU promotion gate therefore failed: **NO_NATIVE_CPU_PROMOTION**.

The earlier generic-build software instruction reduction of 1.1770% remains
valid within its own boundary. This native result does not establish the
Arena's retired-instruction ordering. The hosted runner's earlier capability
probe exposed no supported hardware instruction event.

## Source and decision

The baseline remains `bc704eebed4e009bc66af1a849f18315c11f1926`.
The candidate is exactly that source plus one `#[inline(always)]`
attribute on `eval_node`; its `src` tree is
`de6696fcecbe99e6fcab5bb68c5974e1e9a04e49`.
The generic executable SHA-256 is
`a76e2bbfe07ce80b204937548b7a00524bee1bff113fe19c9e1244ed93443f46`.

**Decision:** retain the inline change as a non-promoted experiment with warranted
bounded generic compatibility. Keep [Arena PR #398](https://github.com/leanprover/lean-kernel-arena/pull/398)
on its existing qualified source. Native nine-large qualification remains UNKNOWN
for this different executable; no further native qualification is required to
reject this CPU promotion. No score or rank improvement has been established.

The highest-leverage unresolved measurement is the full Arena-native Mathlib
instruction score for the already submitted release, through the normal full
workflow after integration or an equivalent maintainer-run workflow.

To replay the artifact join, place the original generic ZIP as `original.zip`
and the ten new ZIPs named in `artifact-metadata.json` beside that metadata.
From this directory, run `python3 verify_artifacts.py --directory ARTIFACT_DIRECTORY --manifest ../flash-upstream-repair-20261126/official-inputs.json --out replay-result.json`.
The original generic ZIP is also retained at the pinned candidate branch's
`experiments/flash-eval-dispatch-inline-20261126/full-result.zip`.

Canonical Research State reconciliation remains pending because its current fetch
was unavailable. This committed outcome and capsule preserve the result meanwhile.
