# QCKN V2 Lean Compounding Falsification Design

## Status

Preregistered bounded experiment. This branch is not a champion branch, a V2 release, or an official Arena submission.

The frozen QCKN V1 bases remain unchanged. The first V2 finite-capability result is frozen at RealityGraph commit `a78cb2b83ca792225df1b7cfe1a1f3b62a8f136c` on branch `qckn-v2-compounding-falsification-v1-frozen`, qualified by Actions run `35338238538` and artifact digest `sha256:399a573173fbea6eb943e7304b0952110dff874484735217ac89bc89ec12e028`.

## Question

Does the already-earned transition

```text
DEPENDENT COMPOSITION
-> INDEPENDENT RECERTIFICATION
-> STANDALONE PROMOTION
-> RE-MINIMISE ACTIVE
```

survive unchanged when the capabilities operate on a real Lean kernel and a held-out Arena workload?

The experiment must answer this before any general Lean adapter is built.

## Starting Evidence

The starting point is the QCKN leader plus recurrent-beta R1 at commit `2f1c8ac4d7da5410fae6fd99fd9b52fc2ae3dabf`.

Hosted run `35305427939` established:

- beta-ladder: `50,879,386,730 / 1,481,034,436 = 34.353953x`;
- grind-ring-5: `2,340,267,586 / 2,335,318,064 = 1.002119x`;
- Mathlib: `810,139,288,192 / 811,450,388,634 = 0.998384x`;
- exact acceptance on all three workloads;
- promotion failed because Mathlib did not improve by the declared `0.1%` threshold.

That failure is the typed residual. It is not weakened or discarded.

Hosted activation-atlas run `35327857819` then established:

- beta-ladder activations at depth `64+`: `96.7984%`;
- Mathlib activations at depth `64+`: `0%`;
- the atlas was observational only and promoted no selector.

Hosted residual-census run `35326638003` independently routed unrelated next Mathlib work to `R3_CONVERSION_FORCE_PRESSURE`. The present experiment therefore does not claim that the depth selector solves Mathlib's remaining cost; it only asks whether the selector removes the R1 collision while retaining and transferring R1.

## Fixed Capability Model

The common QCKN interface uses the frozen RealityGraph `FiniteCapability`, `compose_capabilities`, `CapabilityGraph`, `Ledger`, and `CompiledPresent` implementations.

Three capability identities are constructed:

1. `lean-r1-context-projector-v1`: maps finite raw inference contexts to typed recurrent-beta activation buckets.
2. `lean-depth64-selector-v1`: maps activation buckets to `ENABLE` or `DISABLE`.
3. `lean-r1-depth64-standalone-v1`: the separately recertified standalone materialisation of their dependency-bearing composition.

The dependent composition keeps both parents as dependencies. Dependencies may be cleared only by minting a new standalone identity after independent Lean authority succeeds.

## Frozen Acquisition Cost

The selector portfolio and order are fixed before the held-out run:

```text
[0, 8, 32, 64]
```

One acquisition-search unit is one threshold candidate inspected against the same source/protected activation contract:

- retain at least `90%` of beta-ladder R1 activations;
- expose exactly `0` observed Mathlib R1 activations.

This yields cold acquisition cost `4`. Authority executions, builds, instruction counts, and semantic checks are reported separately and never folded into acquisition search.

No later run may change the portfolio, its order, the `90%` retention floor, the zero-exposure rule, or the meaning of one search unit.

## Arms

All arms use the same selector portfolio and authority.

- `COLD`: no compiled present; inspect all four candidates.
- `WARM`: restart from the compiled verified present with discovery disabled; use the trusted standalone depth-64 capability directly; search cost `0`.
- `RAW_HISTORY`: receive causal ledger text but no compiled capability; inspect all four candidates.
- `SHAM`: receive a matched-cost compiled capability with the wrong certificate/selector; reject it and inspect all four candidates.
- `ANCESTOR_ABLATION`: remove the retained standalone capability; inspect all four candidates.

The required causal pattern is:

```text
WARM = 0 < COLD = RAW_HISTORY = SHAM = ANCESTOR_ABLATION = 4
```

## Held-Out Workload

The target is fixed as the existing Arena workload `perf/magma-list-deep-n21` at Arena commit `510fbfead6f02bed1a0179d01729a6ddf5bfd06d`.

It is structurally related through deep binder/evaluation pressure but was not used by the R1 activation atlas that discovered the selector. The source remains `perf/beta-ladder`. `perf/grind-ring-5` and `mathlib` remain protected controls.

No replacement target is permitted after the hosted run starts.

## Independent Lean Authority

The selected standalone candidate and an exact R1-disabled ablation are built from the same branch and toolchain. Authority must establish:

1. exact exit-status and stdout parity on beta-ladder, held-out target, grind-ring-5, and Mathlib;
2. beta-ladder deterministic Callgrind instruction speedup of at least `2.0x`;
3. held-out target deterministic Callgrind instruction speedup of at least `1.01x`;
4. grind-ring-5 deterministic Callgrind instruction speedup of at least `0.95x`;
5. Mathlib deterministic Callgrind instruction speedup of at least `0.999x`.

Every arm cites this same authority result. Warm execution may remove acquisition search, never verification.

If the held-out target misses `1.01x`, or any protected gate fails, the experiment is RED. The result must identify the exact failed gate and retain it as an obstruction; the workload, threshold, and metric may not be changed to rescue the claim.

## Promotion, Retention, and Restart

Before promotion, ACTIVE contains the projector, selector, and standalone candidate. After independent authority and standalone promotion:

- ACTIVE contains only `lean-r1-depth64-standalone-v1`;
- parent capability identities and certificates remain in PROVENANCE;
- RESERVE is empty under the main bounded contract;
- a separate recovery negative control declares selector recoverability and must reject deletion with `RecoveryUnavailable`.

The post-contraction `CompiledPresent` must restart byte-for-byte and digest-for-digest. Restart with discovery disabled must reproduce the WARM arm and preserve the finite protected decision table.

## Alternatives Rejected

Benchmarking every selector on full Mathlib would make the probe needlessly expensive without changing the fixed finite acquisition semantics. A synthetic-only replay would not establish real Lean transfer. The chosen design uses structural evidence for candidate acquisition and performs the expensive real authority once on the selected identity, identically for every arm.

## Success Boundary

Success warrants only this claim:

> On one frozen Lean-kernel capability family and one preregistered held-out Arena workload, a compiled, independently recertified composition reduced new selector-acquisition search from four candidates to zero while preserving unchanged authority, exact acceptance, and a smaller active present.

It does not establish universal transfer, open-ended optimisation, arbitrary ontology invention, or a finished QCKN V2.
