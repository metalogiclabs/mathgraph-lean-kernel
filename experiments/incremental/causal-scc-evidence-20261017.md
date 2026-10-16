# 17 October 2026 — Same-binary SCC reclosure causal qualification

**WARRANTED_BOUNDED:** retained SCC closure is faster than complete SCC reconstruction under the same compiled binary and pinned genuine Lean/Std environment; complete warm transaction benefits only the unrelated edits in the tested paired CI sample. This neither proves asymptotic change-proportional verification nor establishes a universally faster end-to-end check.

- Qualified source **730b1fb54a96a7145ac41f122c386748705f228e**.
- [Successful Actions #38975932789](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38975932789), [artifact #12079826924](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38975932789/artifacts/12079826924), downloaded archive SHA256 **8ae8ba3a3c5b461838dd9533f380e935a851e5baf08b5f75f40fe854f527aa20**, equal to GitHub-provided archive digest.
- Original pinned Std exports: 3,436 flattened obligations, **243/243 required protected gates**. Expanded pinned Std exports: 11,653 obligations, **226/226 gates**. Native/Python independent full-index equality, fresh Rust plus official/paranoid C++ full checks, authenticated source owner, actual selected Rust kernel, HMAC receipts, corruption and cold controls retained.
- The A/B has one index-session executable and same source-owner producer, policies and selected kernel. The only variable is retained SCC versus complete SCC finish, with the choice in signed producer provenance. Five paired repeats alternate order. Cold baseline construction excluded.

| Workload / edit | Complete SCC warm | Retained SCC warm | Full-transaction decision |
| --- | ---: | ---: | --- |
| 3,436 early | 0.197711s | 0.195786s | 3/5, **NO_SPEEDUP** (95% ratio interval 0.905–1.237) |
| 3,436 unrelated | 0.179794s | 0.160614s | 5/5, **SPEEDUP** 10.67% |
| 11,653 early | 0.788004s | 0.756307s | 3/5, **NO_SPEEDUP** (0.863–1.058) |
| 11,653 unrelated | 0.775873s | 0.721437s | 5/5, **SPEEDUP** 7.02% |

**Direct SCC phase:** early 3,436: 15.076ms→0.426ms; early 11,653: 64.985ms→1.733ms. The retained path recomputes 3 SCCs early and 1 unrelated SCC in both profiles. Phase-level improvements are **not** promoted as whole-pipeline savings.

**Failed provenance preserved:** [first A/B run #38973328844](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38973328844) failed the newly introduced false strict NDJSON byte-parity comparison; its original protected qualifications were green. The revised test enforces complete *typed* identity parity of an independently reconstructed full composite plus authentic source and fresh kernel oracles.

**Current residual:** full-index JSON transfer, complete receipt serialization, immutable composite materialization/full parser and whole-input hashing. A separate sparse-index wire candidate is in [research/incremental-sparse-index-wire-20261017](https://github.com/metalogiclabs/mathgraph-lean-kernel/tree/research/incremental-sparse-index-wire-20261017). Its claims require their own exact-source qualification.
