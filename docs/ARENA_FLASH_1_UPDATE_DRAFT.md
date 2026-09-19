# Draft: Arena MathGraph bump to Flash 1

**Do not submit until the Flash 1 RC1 release gate passes.**

Proposed upstream change: update only `checkers/mathgraph.yaml` to the frozen MathGraph revision in `release/flash-1-rc1/mathgraph.yaml`.

## Draft PR title

`checkers: bump mathgraph to Flash 1`

## Draft PR body

Updates the existing MathGraph checker to the next verifier-preserving performance candidate.

The revision remains a fork of `intgrah/sokonanoda`; the current Arena sokonanoda entry is unchanged.

The retained changes come from profiling and controlled intervention around repeated evaluation / environment / application work. The final candidate is a **composition** rather than a ranking of independent patches: one rigid-inference intervention was nearly neutral on the newer present by itself but became useful when combined with application hash-consing preallocation.

Pre-submission evidence is intentionally separated from Arena authority:

- frozen candidate revision: `a342c74f6eb913c25c6dae4138158023d1b9aa6a`;
- complete pinned Arena semantic qualification: **fill from run 35418749010**;
- semantic mismatches: **fill from run 35418749010**;
- same-runner native-PGO Mathlib comparison against Arena-pinned sokonanoda `28c03d0103e004610e4d47a4828965efb2b70af9`: **fill from run 35418749010**;
- broader cslib / cedar / init / grind-ring-5 panel: artifact from run 35418749010.

The local timing results are not claimed as Arena ranking results. The purpose of this PR is to obtain the Arena's authoritative instruction-count measurement on the exact pinned revision.

### Claim boundary

This PR does not claim formal soundness or equivalence to a formal specification of Lean. It claims only the recorded differential semantic qualification and the implementation changes visible in the pinned source. If official Arena performance does not improve the existing MathGraph entry, that result should control whether this candidate is retained as an Arena performance release.

### AI/tool disclosure

AI coding and analysis tools were used extensively during exploration, experiment design, implementation assistance, and documentation. The retained claims are based on reproducible source revisions, semantic replay, controlled comparisons, and Arena measurements rather than model assertions.

### Attribution

MathGraph is derived from Jeremy Chen / intgrah's `sokonanoda`, with that lineage preserved in the repository and checker description.
