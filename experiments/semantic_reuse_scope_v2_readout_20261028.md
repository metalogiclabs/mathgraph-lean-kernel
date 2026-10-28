# Graph-Native Nucleus V2 — complete-Mathlib source-prefix scope readout (28 October 2026)

## Evidence authority and exact transport

- Isolated source branch: [`research/semantic-reuse-scope-v2-20261028`](https://github.com/metalogiclabs/mathgraph-lean-kernel/tree/research/semantic-reuse-scope-v2-20261028), measured commit `6d1ebdb2e9e6b32409fcc03bd1aef88f306e87d2`.
- Successful [native full-Mathlib CI 40663072252](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/40663072252); evidence artifact `graph-native-nucleus-v2-full-mathlib-6d1ebdb2e9e6b32409fcc03bd1aef88f306e87d2`, GitHub artifact ID `12806040704`; independently downloaded ZIP SHA-256 `fe178fdb9c8792d0821e3b3b1ab8a2ea116d5b30d5f6d31eec9b36ede51e5434` and ZIP integrity PASS.
- Complete machine report is retained byte-for-byte as [`semantic_reuse_scope_v2_result_20261028.json`](semantic_reuse_scope_v2_result_20261028.json). The experiment protocol was frozen before this input was exposed: [`semantic_reuse_scope_v2_protocol_20261028.md`](semantic_reuse_scope_v2_protocol_20261028.md).
- Native checker binaries from the *same Git revision*: ordinary SHA-256 `38b74727cf38e8fc70d3faac12b9a30f913ef333e2230d86bfd7d607e7387ebd`; opt-in V2 diagnostic SHA-256 `40c403840cc9b387ddfa67106263a25b6689e549a6a6a352a02d31779ea16fad`.
- Input: original Lean Arena commit `b83254de5146ef34147ab82a48edbe1856b0edcc`, 6,184,415,052-byte Mathlib SHA-256 `22c5de83469408950005589a3bc5ef5157c65549b5a802f85d567c29151306a6`.
- Native execution: 4 workers, identical JSON stdin config; both exited successfully with byte-identical stdout `Checked 718577 declarations with no errors`. Source-level V1/V2 contract and real-export tests passed on CI. No evaluator value was reused or proof rule changed.

## Observed context partitions in one execution

Within this run, the 1/256 *source-pointer-identity*-selected closed-expression cohort reported 515,671 existing-cache hits, 16,434 first sampled cache misses, 97,746 subsequent cross-reset sampled misses, 0 same-generation misses, 0 excluded, and 146,636 resets. All 97,746 recurrences classified without unmatched identities:

| Read-only context class | Cross-reset events | Fraction of cross-reset cohort |
| --- | ---: | ---: |
| Later prefix; all **direct syntactic** source references visible at prior cutoff | **94,216** | **96.3886%** |
| Temporary nested-inductive context on at least one side | 3,472 | 3.5520% |
| Exactly equal source cutoff, no temporary extension | 56 | 0.0573% |
| Regressed source cutoff | 2 | 0.0020% |
| Source references blocked/unknown under the capped traversal | 0 | 0% |

The predeclared V2 gate required at least 1,000 advanced-visible events and at least 20% of cross-reset events, with peak RSS no more than 1.15× baseline. Both numerical requirements passed (`94,216`, `96.3886%`); RSS ratio was `1.013921`. The machine decision is therefore **`INVESTIGATE_TRANSITIVE_PREFIX_PROOF_AND_COST_WEIGHTED_SLICE`**. This is *eligibility to investigate*, not warranted cross-reset semantic equality.

**Important sample-design limitation:** V1's earlier run counted 72,249 recurrences among 87,951 sampled misses; V2 found 97,746 among 114,180. The 1/256 selector hashes the **process-local source pointer address**, not a stable exported expression ordinal. Different processes can choose materially different cohorts under address layout and heavy-tailed reuse. Neither delta is an improvement or regression in the checker. In particular, do not multiply the sampled results by 256 to claim an unbiased whole-corpus opportunity. A future cost experiment requires stable source-ID sampling or full-event accounting.

## Cost warning: recurrence is not a speedup

The diagnostic timed *only the sampled `eval_no_cache` body* after the source-support observation. It accumulated `23,246,207 ns` (about **23.25 ms**) across 94,216 advanced-visible recurrences, approximately **247 ns inclusive per event** in the sampled cohort. Sampled recurrent head kinds were mostly `Const` (52,954), `App` (23,025), `Pi` (11,871), `Lambda` (6,548), `Sort` (2,651), and `StringLit` (695); inclusive cost by head was `App` 15.11 ms, `Const` 6.72 ms, `Pi` 1.03 ms, and smaller elsewhere.

These counters include nested evaluations and timing noise; they do not measure unique avoided work, lookup/transport cost, retired machine instructions, or causal savings. A persistent representation may cost **more** than re-evaluating a cheap expression. They must not be compared directly with baseline whole-process CPU time or projected linearly to all expressions.

Operationally, the ordinary binary observed 73.63 s wall / 258.70 s user CPU / 7,750,612 KiB peak RSS. The instrumented diagnostic observed 81.26 s wall / 268.60 s user CPU / 7,858,508 KiB RSS. These are **not** speedup pairs: the feature adds instrumentation and the runs were sequential, not a matched repeated A/B optimization. Peak RSS increase was 1.3921%, below the protocol's diagnostic intrusiveness gate.

## Epistemic states and next cheapest experiment

- **WARRANTED within exact native boundary:** both checker variants accept the same complete pinned corpus; machine counts and partition sums agree; raw artifact digest/integrity verified; V2 is read-only; feature-gated diagnostic tests passed.
- **CANDIDATE:** repeated pointer-identical source-global closed evaluations are overwhelmingly found under later source prefixes where direct expression references were already visible. The earlier source-visible prefix may preserve their denotation, but this is **not** established by the present syntactic walk.
- **UNKNOWN:** transitive dependencies (including reductions/recursors), universe substitutions, expected typed judgment, transparency, temporary context, value lifetime and thread safety, actual cache retrieval cost, full-source representativeness, savings in guest Ir/hardware PMU, and transfer beyond this source/commit.
- **REJECTED as promotion reasoning:** raw recurrence count ⇒ speedup; source pointer equality ⇒ semantic equality; syntactic support ⇒ deployable authorization; or any claim of an already implemented graph-native persistent semantic cache.

**Decision:** Continue the independently frozen V3 16→64 MiB *in-lifetime* cache budget intervention first. It requires no semantic-value transport across reset. If it earns a paired CPU screen, test guest instructions and frozen invalids. Separately, if a persistent source quotient is pursued, first obtain a stable-ID, cost-weighted census (prioritizing expensive `App` contexts), a proper source-prefix/transitive-support proof or independently checked certificate, and a bounded lifetime-safe replay mechanism with mutations. Require native whole-Mathlib and strong fair baseline before any performance or correctness promotion.
