# MDA Performance Convergence V2 — Lean Kernel Arena

**Status:** frozen protocol, pre-result  
**Repository:** `metalogiclabs/mathgraph-lean-kernel`  
**Branch:** `mda/performance-convergence-v2`  
**Semantic convergence result:** `VERIFIED_BIDIRECTIONAL_SEMANTIC_FRONTIER_CONVERGENCE`  
**Semantic result run:** `34804723050`  
**Full present:** `d6a73279e6765e637f9741180cefbd7ef957d8e5`  
**Genesis base:** `16ccc0ed1c28961e411452d1c1a608761d73929e`  
**Pinned Arena:** `ac1c13762de41b594fa24b90ede8cfd97ac6a765`

## Question

The semantic-only solvent collapsed the six retained MathGraph capabilities to one soundness atom.

Now add a second constraint: **performance**.

Within the same frozen six-capability class, do GENESIS and SOLVENT recover the same minimum-cardinality configuration frontier that:

1. remains semantically lawful; and
2. preserves the full present's bounded performance vector?

This tests whether performance structure can be earned from below and independently survive contraction from above.

## Why only eight masks are measured

V1 exhaustively tested all 64 masks from both directions before any V2 performance result.

The exact common semantically lawful set was:

`[2, 3, 10, 11, 30, 31, 62, 63]`.

V2 freezes that set as the admissible semantic domain and introduces no new capability atom.

This is not post-hoc performance selection: the filter is entirely semantic and precedes V2 performance measurement.

## Capability atoms

| Bit | Commit | Capability |
|---:|---|---|
| 0 | `801cb6d918d0e383e4c6a3c6017ef945d42a0698` | equal-hint short asymmetric-spine optimization |
| 1 | `2de1895a52d21ad266b77002defe3e6bc69bbcfd` | reject underived/orphan recursors |
| 2 | `91ba5db4029290b257a08494559ec3283cddbee3` | wide framed environments for exact deep read sets |
| 3 | `eaf479a135c02e0daad6760eff9e049dd9f63576` | exact wide-read/projected-environment caches |
| 4 | `5daa4f66c1fa63b44d2dd02e96bd7303e6ec0f71` | exact environment keys past 64 loose variables |
| 5 | `d6a73279e6765e637f9741180cefbd7ef957d8e5` | bottom-up wide read-set memoization + one-pass projection |

A mask bit means retain that capability.

## Construction

For each admissible mask, independently construct the same configuration in both directions.

### GENESIS

Start at `16ccc0ed...` and apply selected capability patches in chronological bit order.

### SOLVENT

Start at `d6a73279...` and revert unselected capability patches in reverse chronological bit order.

The normalized executable source payloads must match before performance convergence can pass.

## Semantic gate

Each direction must again pass unchanged:

- `cargo test --release --locked`;
- `init-prelude` accept;
- `extra-rec` reject;
- `rec-missing-ih` reject;
- `proj-of-stuck-prop` reject;
- `proj-of-subst-prop` reject.

A semantic regression excludes the configuration before performance preference.

## Performance measurement

Because hosted GitHub runners do not expose the hardware retired-instruction counter used by the Arena's official Mathlib ranking, this experiment uses a frozen **Callgrind instruction-count proxy**.

The performance probe set is frozen before candidate measurements:

- `perf/grind-ring-5`
- `perf/app-lam`
- `perf/beta-ladder`
- `perf/let-ladder`

These are existing Arena performance tests already used in the repository's pre-V2 profiling workflows. No test is selected from V2 outcomes.

Each candidate is built in the same fixed experimental mode:

`cargo build --release --locked`

No `target-cpu=native` and no PGO are used in V2 so cross-run code generation is not intentionally specialized to runner hardware.

For each direction and each performance case:

- run under Valgrind Callgrind;
- require checker exit 0;
- record Callgrind `summary:` instruction count.

## Performance sufficiency

Performance sufficiency is defined relative to the full-present mask `63` **within each direction separately**.

For direction `D` and test `t`, let:

`I_D(m,t)`

be the Callgrind instruction count.

A semantically lawful mask `m` is performance-sufficient in direction `D` iff for every frozen performance test:

`I_D(m,t) <= 1.02 * I_D(63,t)`.

The 2% allowance is frozen before results to absorb minor measurement/runtime-library variation. It is not an Arena score tolerance.

## Developmental preference

Among performance-sufficient masks, prefer fewer retained capability atoms.

Let:

`F_G^perf`

and

`F_S^perf`

be the minimum-retained-count performance-sufficient frontiers in GENESIS and SOLVENT respectively.

The V2 convergence verdict passes iff:

1. every measured mask remains semantically lawful in both directions;
2. normalized source payloads match for each mask;
3. both performance frontiers are nonempty;
4. `F_G^perf == F_S^perf`.

The workflow additionally reports per-test instruction ratios and Pareto relations.

## Claim boundary

A pass establishes only:

> Within the previously frozen semantically lawful eight-mask class, under the fixed release build and four frozen Arena performance probes, genesis and solvent independently recover the same minimum-cardinality configuration frontier that preserves the full present's Callgrind instruction vector within 2%.

It does **not** establish:

- official Lean Kernel Arena Mathlib performance equivalence;
- global performance optimality;
- correctness outside the protected replay;
- that Callgrind is numerically interchangeable with the Arena's hardware retired-instruction measurement;
- convergence in arbitrary continuation languages.

Official Arena promotion still requires the Arena's own authoritative Mathlib performance measurement.
