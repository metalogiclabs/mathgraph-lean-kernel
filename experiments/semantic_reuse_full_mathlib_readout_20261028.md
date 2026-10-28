# Graph-native nucleus: full-Mathlib identity-census preflight (28 October 2026)

## Frozen authority and lineage

- Successful workflow: https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/40657552900
- Evidence artifact: `graph-native-nucleus-full-mathlib-83134470c98656d82dddb834d60b0ebe955b84d3`
- Evidence artifact ZIP SHA-256: `f1d90c2ef1f0c5fd039dcc805df6408861e7390fda81503b64f8fcb954c1684e`
- Checker commit: `83134470c98656d82dddb834d60b0ebe955b84d3`; source tree matched tested local checkout.
- Lean Arena commit: `b83254de5146ef34147ab82a48edbe1856b0edcc`.
- Complete Mathlib input: 6,184,415,052 bytes; SHA-256 `22c5de83469408950005589a3bc5ef5157c65549b5a802f85d567c29151306a6`.
- Exact machine report, copied without changing its claims: `semantic_reuse_full_mathlib_result_20261028.json` in this directory.
- Superseded first attempt: https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/40656074833 — **invalid measurement**; upstream-style flags were passed to a JSON-config-only CLI. The fixed native adapter and its regression test preceded the successful run.

## Observation and qualification

Two same-revision checker binaries (plain and feature-gated census) independently accepted **718,577 declarations** with identical stdout (`Checked 718577 declarations with no errors`). Both exited successfully. The 1-in-256 sampled, **source-global, closed, unsubstituted-expression** census reported:

| Measured count | Value |
|---|---:|
| Sampled evaluation cache hits | 787,731 |
| Sampled evaluation cache misses | 87,951 |
| Misses first encountered | 15,702 |
| Misses repeating after a cache reset | 72,249 |
| Cache resets observed | 146,638 |
| Candidate share of sampled misses | 82.1469% |
| Candidate share of all sampled eligible accesses | 8.2506% |

The original predeclared *next-stage eligibility gate* required at least 1,000 recurrent misses and a recurrent fraction of at least 5% of sampled misses. Both thresholds were exceeded; its recorded decision is **`INVESTIGATE_TYPED_SCOPE`**.

**WARRANTED within the native-run boundary:** both binaries completed the frozen full-Mathlib positive workload, matched on stdout, and emitted the above diagnostic identity counts. **CANDIDATE only:** many repeated exact expression identities cross ephemeral cache resets. **UNKNOWN:** whether those expressions are equal under the minimum typed/source-visible support, how many machine instructions could be saved, whether persistence would remain sound under changed declarations, and any real speedup.

For transparency, the uninstrumented and probe runs recorded wall times of 103.99s and 99.43s and peak RSS of 7,706,188 and 7,786,752 KiB, respectively. These are **not** speedup measurements: the sequential run order, cache warmth, instrumentation, and lack of a reuse implementation make their difference non-causal.

The `excluded=0` field does **not** mean no expression was excluded: this preflight only calls the census on eligible sampled expressions and does not count excluded expressions in the live path. Pointer-address-based sampling is stable *within* a run but may select a different subset across process address-space layouts. Neither affects the narrowly stated candidate-count observation, but both prohibit broad workload-wide or semantic-reuse claims.

## Cheapest next decisive experiment

For a frozen sample of the **cross-reset candidate** identities, record a minimum typed support/visibility fingerprint (declared constant dependencies, universe substitutions, source epoch, expected judgment) and compare it across occurrences. Independently check a proposed persistence-key equality against the original checker on positive and mutation-negative workloads. Attribute native instruction cost specifically to genuinely safe recomputations rather than cached hits; include the existing caches and hash-consing as the fair baseline. Only then can any subset be promoted toward reusable semantics or a justified performance hypothesis.

No normal checker acceptance rule was changed; the census is behind an opt-in `reuse-probe` Cargo feature and never returns cached values.
