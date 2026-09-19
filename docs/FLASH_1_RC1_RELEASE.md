# Flash 1 RC1 — Arena release candidate

Status: **qualification in progress / not yet proposed upstream**

## Frozen source

- Repository: `metalogiclabs/mathgraph-lean-kernel`
- Qualification/documentation branch: `flash-1-rc1`
- Frozen source branch: `flash-1-rc1-source`
- Frozen candidate source revision: `a342c74f6eb913c25c6dae4138158023d1b9aa6a`
- Lineage: fork of Jeremy Chen's / intgrah's `sokonanoda`
- Current Arena sokonanoda pin: `28c03d0103e004610e4d47a4828965efb2b70af9`
- Pinned Arena suite used by the qualification workflow: `510fbfead6f02bed1a0179d01729a6ddf5bfd06d`

The frozen source activates four retained/candidate mechanisms:

- `DIRECT_VAR_EVAL`
- `DIRECT_FRAMED_PRUNE`
- `RIGID_INDUCTIVE_NEUTRAL`
- `APP_HC_PREALLOC`

The latter two are frozen together because the measured objective is non-additive: Rigid V2 was nearly neutral on the latest present by itself, while the Rigid V2 + app_hc composition materially improved the Mathlib result.

## Existing authority

### Qualified Flash champion

Run 35412479165:

- 409/409 semantic parity
- 0 mismatches
- seven-replay same-runner Mathlib duel
- sokonanoda median: 88.76 s
- Flash champion median: 87.39 s
- local wall-time margin: 1.57%
- essentially unchanged median RSS

This is pre-submission evidence, not an Arena instruction-count result.

### Rigid V2

Run 35415353691:

- full 409 quotient/congruence authority: PASS

### Rigid V2 + app_hc composition

Run 35413932085:

- focused semantic/status parity: PASS
- Mathlib champion: 92.97 s
- Rigid V2: 92.87 s
- combined: 90.10 s
- combined vs champion: 3.19% faster
- combined vs Rigid V2: 3.07% faster
- `FLASH_RIGID_V2_APPHC_COMPOUNDING_PASS`

This run motivated freezing the exact composition as source. It is **not** by itself the final full-corpus release authority.

## Release gate

The dedicated workflow `.github/workflows/flash-1-rc1-qualification.yml` must pass all of:

1. exactly 409 pinned Arena exports are built;
2. exact output/exit-status parity against the previously qualified Flash champion on all 409 exports;
3. an Arena-style native-PGO build is used for the performance comparison;
4. a seven-replay same-runner Mathlib duel is run against the current Arena-pinned sokonanoda revision;
5. a broader PGO regression panel is recorded for cslib, cedar, init, and grind-ring-5;
6. the release decision emits `FLASH_1_RC1_RELEASE_GATE=PASS`.

No upstream Arena update should be proposed before that gate passes.

## Claim boundary

### Claimed if the release gate passes

- The frozen candidate preserves the tested Arena behavior of the qualified Flash champion on the complete pinned 409-export corpus.
- The candidate has a reproducible same-runner performance comparison against the current Arena-pinned sokonanoda revision.
- The retained performance changes were selected by profiling, controlled intervention, composition tests, semantic replay, and ablation rather than by a single benchmark measurement.

### Not claimed

- Formal soundness of MathGraph.
- Equivalence to a formal specification of Lean.
- That local wall time or Callgrind predicts the official Arena instruction ranking exactly.
- That Flash 1 is #1 in Arena before the Arena itself measures the pinned release.
- That every active mechanism is globally optimal or independently beneficial.
- That QCK/QCKN terminology is required to understand or trust the implementation.
- That AI-generated code or analysis is correct without the recorded external verification.

## AI / tool disclosure

AI coding and analysis tools were used extensively during exploration, experiment design, implementation assistance, and documentation. Retained claims are intended to rest on reproducible source revisions, semantic replay, independent test outcomes, and Arena measurements rather than on model assertions.

## Community-facing principle

The public unit of contribution is a small inspectable mechanism with:

- explicit upstream lineage and authorship;
- a concrete performance hypothesis;
- semantic replay;
- negative controls / ablation where applicable;
- exact evidence links and hashes;
- rejected alternatives preserved when they are informative;
- conservative claims.

The Arena remains authoritative for comparative ranking.
