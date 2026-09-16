# RealityGraph Selective Representation V1

## Status

Experimental branch. No upstream Arena PR.

## Provenance

MathGraph is a Metalogic Labs derivative of the nanoda / still-nanoda / sonanoda / sokonanoda lineage. The existing Apache-2.0 license and upstream attribution remain authoritative. This programme does not claim a clean-room or independent implementation.

## Objective

Build a distinct MathGraph execution architecture on top of the sound, complete Rust checker by making representation choice an explicit, verifier-gated runtime capability rather than a fixed global evaluator policy.

The target is not to copy nanoclo wholesale. Official Arena evidence shows delayed substitutions are excellent on beta-heavy workloads but can be materially worse on large whole-library workloads. The target therefore is a selective multi-representation evaluator:

    ordinary retained value/closure execution
      + structural residual fingerprint
      + bounded alternate representation
      + exact semantic firewall
      + independent consequence measurement
      + ablation

## Evidence entering V1

1. The current Rust MathGraph checker is complete on the scored Arena set and is materially faster than its sokonanoda parent on large workloads.
2. The JavaScript discovery kernel showed that a 3/4-argument LocalDef closure selector was semantically safe but causally neutral: at both 2M and 4M it produced zero semantic-step, node-construction, status, or frontier improvement on `init-prelude` and `perf/grind-ring-5`.
3. The same experiment preserved the `perf/fueled-chain` route and `perf/shared-subterm`, so it is useful negative evidence: arity alone is not a sufficient selector.
4. Arena comparison data shows a strong representation tradeoff: delayed-substitution kernels dominate `perf/beta-ladder` / `perf/let-ladder`, while the retained MathGraph/sokonanoda lineage is far stronger on whole Mathlib. This is the exact mixed-evidence trigger for selective representation search.

## V1 design law

A selector may depend only on structural execution state available before the result is known. It may not inspect test names, expected verdicts, file paths, or published timings.

Every candidate must satisfy:

- no new wrong verdicts;
- exact retained semantics at the representation boundary;
- unsupported shapes fall back to the retained evaluator;
- independent workload separation before promotion;
- ablation restores the old execution path;
- no benchmark-name special cases.

## First frozen repair portfolio

The initial tournament is deliberately small and orthogonal:

### R0 — retained champion

Current `dulce-de-leche` evaluator unchanged.

### R1 — beta-density selector

Use an alternate delayed-substitution execution path only after a structural prefix demonstrates repeated binder-consuming beta work with no recursor/projection demand. This targets the `beta-ladder` family without globally changing Mathlib execution.

### R2 — environment-pressure selector

Use a compact environment representation when the closure's live de-Bruijn support is much smaller than its environment depth. This builds directly on MathGraph's existing `Framed` / `WideFramed` environment machinery and exact-use analysis.

### R3 — conversion-demand selector

Retain current closures, but alter forcing/materialisation policy when the same structural conversion state repeatedly forces equivalent closure prefixes. This targets `grind-ring-5` and large conversion workloads without changing inference rules.

Only one repair is admitted at a time. Ties remain experimental.

## Measurement order

1. Unit semantic parity tests.
2. `perf/beta-ladder`, `perf/let-ladder`, `perf/app-lam`.
3. `perf/grind-ring-5`, `init-prelude`, `perf/fueled-chain`, `perf/shared-subterm`.
4. magma/list family.
5. full scored Arena correctness gate.
6. Init / Std / Mathlib performance.
7. ablation and final contraction.

## Identity / attribution boundary

If this programme succeeds, the correct description is:

> MathGraph is Metalogic Labs' high-performance experimental Lean 4 checker, derived from the nanoda/sokonanoda lineage and substantially extended with a verifier-guided selective-representation architecture.

It should not be described as clean-room, from-scratch, or independent of sokonanoda while upstream code remains in the implementation.
