# MDA Workload-Constrained Convergence V3 — Lean Kernel Arena

**Status:** frozen protocol, pre-result  
**Repository:** `metalogiclabs/mathgraph-lean-kernel`  
**Branch:** `mda/workload-convergence-v3`  
**Semantic convergence result:** run `34804723050`  
**Full present:** `d6a73279e6765e637f9741180cefbd7ef957d8e5`  
**Genesis base:** `16ccc0ed1c28961e411452d1c1a608761d73929e`  
**Pinned Arena:** `ac1c13762de41b594fa24b90ede8cfd97ac6a765`

## Question

The semantic-only experiment showed that one soundness capability is sufficient for the frozen semantic replay.

This experiment asks the intended second-constraint question on the real workloads that motivated the retained environment machinery:

> When semantic correctness is held fixed and performance on **Mathlib + con-leche** is added as a protected workload constraint, what is the minimum retained capability configuration, and do GENESIS and SOLVENT construct the same source configuration?

Mathlib is the Arena ranking-relevant workload. Con-leche is retained as a frozen negative-transfer/stress workload because pre-existing V113 evidence showed that removing wide-environment machinery can improve Mathlib while catastrophically regressing con-leche.

The workload choice therefore predates this V3 result and is not selected from V3 outcomes.

## Admissible semantic configurations

The exhaustive V1 semantic experiment established the common lawful set:

`[2, 3, 10, 11, 30, 31, 62, 63]`.

Only these eight configurations are measured here.

## Capability atoms

| Bit | Commit | Capability |
|---:|---|---|
| 0 | `801cb6d918d0e383e4c6a3c6017ef945d42a0698` | equal-hint short asymmetric-spine optimization |
| 1 | `2de1895a52d21ad266b77002defe3e6bc69bbcfd` | reject underived/orphan recursors |
| 2 | `91ba5db4029290b257a08494559ec3283cddbee3` | wide framed environments for exact deep read sets |
| 3 | `eaf479a135c02e0daad6760eff9e049dd9f63576` | exact wide-read/projected-environment caches |
| 4 | `5daa4f66c1fa63b44d2dd02e96bd7303e6ec0f71` | exact environment keys past 64 loose variables |
| 5 | `d6a73279e6765e637f9741180cefbd7ef957d8e5` | bottom-up wide read-set memoization + one-pass projection |

## Paired construction

For every mask:

- GENESIS constructs it from `16ccc0ed...` by applying retained capability patches.
- SOLVENT constructs it from `d6a73279...` by reverting contracted capability patches.

The normalized executable source payloads must be byte-identical by SHA-256. Once source identity is established, one canonical build of that source is sufficient for workload measurement; performance is attached to the resulting configuration, not to the historical path used to construct identical source.

## Semantic replay

Before workload timing, each candidate must freshly pass:

- `cargo test --release --locked`;
- pinned Arena `init-prelude` accept;
- `extra-rec` reject;
- `rec-missing-ih` reject;
- `proj-of-stuck-prop` reject;
- `proj-of-subst-prop` reject.

## Workload measurement

Each matrix cell runs on one GitHub-hosted runner.

On that same runner:

1. build the exact full present `d6a73279...` in fixed release mode;
2. measure full-present `mathlib`;
3. measure full-present `con-leche`;
4. build the candidate source in the same fixed release mode;
5. measure candidate `mathlib`;
6. measure candidate `con-leche`.

Build mode:

`cargo build --release --locked`

Checker configuration:

- 4 threads;
- same extensions/axiom settings as the frozen domain contract.

For each workload record:

- exit status;
- wall time;
- user CPU time;
- system CPU time;
- CPU work = user + system;
- peak RSS.

## Relative performance ground

Because GitHub-hosted runners do not expose the Arena's authoritative hardware retired-instruction counter, V3 does **not** claim an official Arena performance result.

Instead V3 defines a same-runner operational workload constraint.

For workload `t`:

`R_cpu(m,t) = CPU_candidate(m,t) / CPU_full(t)`.

A candidate is workload-sufficient iff:

1. it exits successfully on both workloads;
2. `R_cpu(m, mathlib) <= 1.20`;
3. `R_cpu(m, con-leche) <= 1.20`.

The 20% allowance is frozen before candidate results to accommodate hosted-runner measurement noise while still rejecting large negative transfer.

## Fail-fast runtime budget

The full present is measured first in every cell.

For each candidate workload, the wall-clock timeout is:

`max(180 seconds, 4 * full-present wall time for that workload)`.

A timeout is classified as workload-insufficient.

This rule is logically conservative relative to the 1.20 CPU-work threshold: the timeout is deliberately far looser than the acceptance threshold and exists only to stop catastrophic regressions from consuming the whole job.

## Frontier

Among workload-sufficient configurations, minimize the number of retained capability atoms.

Because paired construction must produce byte-identical source, GENESIS and SOLVENT share the same measured configuration value only after their source identity is independently re-established in this run.

The strict V3 verdict passes iff:

1. all eight masks reconstruct from both directions;
2. source payloads agree pairwise;
3. semantic replay passes for every admissible mask;
4. at least one workload-sufficient configuration exists;
5. the minimum-cardinality workload-sufficient frontier is reported exactly.

## Claim boundary

A pass establishes a bounded workload invariant under:

- the eight semantically lawful V1 masks;
- same-runner relative CPU-work measurement;
- Mathlib + con-leche;
- fixed release build;
- 20% operational tolerance.

It does **not** establish the official Arena instruction-count ranking. Any release/promotion claim still requires the Arena's authoritative measurement environment.
