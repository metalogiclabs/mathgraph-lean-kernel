# Retained SCC delta reclosure — evidence checkpoint (2026-10-17)

**Status: WARRANTED_BOUNDED correctness and mixed warm economics.** This does not prove universal reuse correctness, an asymptotic change-proportional update, or causal speedup against the previous full-SCC indexer. The new branch inherits the previously qualified producer-delta trust assumptions.

## Lineage and exact source
- Prior qualified producer-delta source: `4496042c75368f6c35675a9b131c960080afa518`; CI [38945728644](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38945728644).
- Isolated implementation: branch `research/incremental-retained-scc-20261017`.
- Tested source: `134c46dfb94eec49deec0ff9a060def23469dd40`.
- Exact-source successful CI: [38965409997](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38965409997), job `117190543174`.
- Archived compact [artifact 12075791569](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38965409997/artifacts/12075791569), 2,729,970 bytes; independently downloaded ZIP and GitHub artifact digest both SHA-256 `c28eb4c187788ff9699329f68209a78f409a84f32faca22f3fc2c79b65488112`.

## Exact mechanism
The production identity session now retains the baseline SCC partition, condensation/reverse graph, negative lookup facts, per-component closure hashes and builtin closure references. For authenticated simple replacement deltas with unchanged declaration identity/dependency topology and no added name rows, only the changed SCCs and their reverse-reachable dependent SCCs are rehashed. Otherwise the original complete-index `finish()` executes; no speculative topology repair is admitted.

The baseline graph is built and checked against original full-index roots on the cold path. The normal `check-selected` parser/kernel still processes every changed composite (including zero-selection malformed cases). The source-owning producer, HMAC issuer, prior acceptance evidence, policy, checking rules and downstream MathGraph resolver were not changed. This is a retained *identity* optimization, not acceptance authority.

## CI correctness
- Rust source/native library suite: 58 passed, including three retained-SCC unit tests for affected-only closure, changed dependency edges/new cycles and added name/builtin fallback.
- Small genuine pinned Lean/Std: **243/243 gates PASS**, 3,436 obligations, early 413 checked / 3,023 reused.
- Expanded genuine pinned Lean/Std: **226/226 gates PASS**, 11,653 obligations, early 672 checked / 10,981 reused.
- Both suites independently compare exact full native/Python identities and original full Rust/C++/paranoid oracle results, plus protected source, authentication, adversarial, corruption, unused malformed-node and cold-replay controls. No required gate failed. The original 197-gate suite was not separately rerun in this focused workflow; its prior-source qualification remains prior evidence, not newly claimed.

## Five-pair CI medians: entire warm producer-to-persistence wall seconds

| Obligations / edit | Warm update | Fresh direct Rust | Median saving | Wins | Bootstrap 95% ratio interval | Gate |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| 3,436 early | 0.216233 | 0.222070 | 2.63% | 4/5 | [0.96150,1.06508] | NO_SPEEDUP |
| 3,436 unrelated | 0.186051 | 0.221164 | 15.88% | 5/5 | [0.81523,0.93228] | SPEEDUP |
| 11,653 early | 0.806547 | 0.922257 | 12.55% | 5/5 | [0.83424,0.90597] | SPEEDUP |
| 11,653 unrelated | 0.815344 | 0.926725 | 12.02% | 5/5 | [0.81966,0.88863] | SPEEDUP |

New CI host and scheduling differ from CI `38945728644`; absolute cross-run timing differences are **not** a causal head-to-head of new indexer versus old indexer. The test qualifies warm-update-versus-direct-Rust economics for this exact source and host. Paired order is fixed apply-then-direct with warm OS cache. Cold setup excluded: small early median 3.098782 s; large early median 11.619009 s.

## Negative results / residual
- First candidate CI [38964973408](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38964973408) failed Rust compilation (refutable optional builtin pattern). [f42575c](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/f42575c6769981f8516bb0b52c84d69def5e5c69) repaired it.
- Second [38965105686](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38965105686) passed 58 Rust tests but its Python historical oracle could not resolve pinned `c5ab126` due shallow checkout. [134c46d](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/134c46dfb94eec49deec0ff9a060def23469dd40) fixed full-history checkout; final run is green.
- In the small early-edit workload the primary economics gate remains **NO_SPEEDUP**, despite positive median savings; negative must not be hidden.
- Full result-index cloning/serialization, full composite materialization and kernel parsing, and baseline authentication/hash still scale with total input. Cold startup and lifetime amortization remain UNKNOWN. The retained SCC implementation and its correspondence with actual Lean kernel dependencies are not machine-proven. The smallest consequential next experiment is separately meter SCC reclosure versus full-index `finish()` on one pinned host and then make receipts sparse without expanding the trust boundary.

The historical producer-delta `4496042` source and its warranted bounded results are not superseded by this mixed economic experiment.
