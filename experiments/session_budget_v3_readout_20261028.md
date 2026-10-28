# Graph-Native Nucleus V3 — 64 MiB session budget rejected by full-Mathlib CPU screen

## Frozen source and authoritative results (28 October 2026)

- [Successful source-pinned V3 CI #40664248417](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/40664248417), exact measured source commit `ac33246693b1e416199843e02212473d3c10c519`, isolated branch `research/session-budget-v3-20261028`.
- Original immutable Mathlib 6,184,415,052-byte input SHA-256 `22c5de83469408950005589a3bc5ef5157c65549b5a802f85d567c29151306a6`, source Arena `b83254de5146ef34147ab82a48edbe1856b0edcc`.
- Evidence artifact `graph-native-nucleus-budget-v3-ac33246693b1e416199843e02212473d3c10c519`, artifact ID `12805904821`, independently downloaded ZIP SHA-256 `9101e39bb64e04b05f6add0405157b6cf2c983f4c825d59001688b822205344c`, integrity PASS. The exact machine JSON is retained as [`session_budget_v3_result_20261028.json`](session_budget_v3_result_20261028.json).
- Same-commit plain release binaries: baseline 16 MiB SHA-256 `8fe119d3dadca422afd8b93e6320cf0252f6568401bc154eaf8b77f841f2a131`; opt-in 64 MiB SHA-256 `64adffce6f7524583ac4aa93474728a3c3adda75a58bcea135def515c86ba350`. The only behavioral source change is the feature-selected per-worker `SESSION_BUDGET` constant, never an environment/pointer transport.
- Frozen protocol: [`session_budget_v3_protocol_20261028.md`](session_budget_v3_protocol_20261028.md). Native default and feature-enabled qualified library suites each passed 44 tests, with two pre-existing missing-fixture panic tests unqualified. All six full-Mathlib runs exited successfully and printed byte-identical `Checked 718577 declarations with no errors`.

## Three alternating paired native checks

Each candidate ran the same 6.18 GB input with four workers and the same native JSON config; order was baseline/candidate, candidate/baseline, baseline/candidate.

| Pair | Baseline user CPU | Candidate user CPU | Candidate / baseline user CPU | Candidate / baseline max RSS |
| --- | ---: | ---: | ---: | ---: |
| 1 | 321.11 s | 371.48 s | **1.156862 (+15.69%)** | 1.011827 |
| 2 | 333.69 s | 368.27 s | **1.103629 (+10.36%)** | 1.017354 |
| 3 | 328.69 s | 364.20 s | **1.108035 (+10.80%)** | 1.020262 |

- The geometric mean of the *three pair ratios* is **1.122585432**: 12.2585% greater user CPU for the 64 MiB candidate. Each pair favored the 16 MiB original. Maximum peak-RSS ratio was 1.020262, below the 1.10 memory gate. Wall-time ratios were 1.8341, 1.1255, 1.0944; the first pair likely includes host scheduling/interference and is not treated as a causal wall-speed theorem. User CPU ratios were consistently adverse.
- The frozen screen required **all three** candidate user CPU ratios below 1, geometric mean at most 0.98, and memory at most 1.10×. The recorded outcome is **`REJECT_64_MIB_BUDGET_SCREEN`**.

## Epistemic conclusion, negative lineage and next residual

**WARRANTED within exact run:** source-owned complete-Mathlib acceptance parity and the recorded three-pair native user CPU/RSS observations with authentic artifact digest. The 64 MiB option fails its predeclared improvement screen decisively.

**REJECTED for performance promotion:** this `16 MiB → 64 MiB` in-lifetime cache-retention intervention. More retained cache state is not a free speedup; there are additional cache/allocator, locality and time-to-reuse costs. The specific causal source of the regression is **UNKNOWN** without instrumentation and is not inferred from the experiment.

**NOT WARRANTED:** general claims that 64 MiB is always slower across hardware, guest-Ir increase, PMU-retired instructions, universal optimum of the original budget, safe persistent cross-reset values, or benefit to a chip/ISA product.

**Next cheapest decisive experiment:** stop tuning cache sizes post-exposure. Retain the earlier V2 source-prefix context partition as *candidate only*. For any graph-native semantic reuse, switch to a stable source-expression identity and **cost-first** measurement after the existing caches, including `infer_nonvar`/conversion (previous full-Mathlib self-cost leaders), expected typed obligation, ambient source cutoff and temporary declarations. Compare actual avoidable guest instructions against representation/proof/lookup costs before implementing a persistent cache. In parallel, existing authenticated incremental checking has previously qualified bounded warm lifecycle gains; reducing whole obligation rechecks may offer more leverage than per-expression retention, but transfer to another deployment still needs its own warrant.
