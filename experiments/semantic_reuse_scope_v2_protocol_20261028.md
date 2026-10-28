# Graph-Native Nucleus V2 — source-scope and cost triage (frozen before full workload)

## Starting evidence and residual

- Source-pinned V1 run: https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/40657552900, checker `83134470c98656d82dddb834d60b0ebe955b84d3`.
- Exactly 72,249 of 87,951 1/256-sampled eligible closed-evaluation cache misses recurred across cache resets on complete Mathlib. No reuse was performed, no speedup measured, and no typed equality established.
- The native checker constructs a new visible declaration prefix (`EnvLimit::ByName`) per checked declaration, sometimes with a temporary nested-inductive extension. Consequently raw expression identity is insufficient for any persistent semantic value.
- Existing evaluator caches and hash-conses must receive fair baseline credit. V1 `excluded=0` did not measure excluded expressions.

## V2 diagnostic experiment (no proof acceptance change)

Retain the same opt-in 1/256 source-global closed-expression identity cohort. For every sampled cache miss, classify the expression head (`Var`, `Sort`, `Const`, `App`, `Pi`, `Lambda`, `Let`, `Proj`, `NatLit`, `StringLit`) and the source context relative to its previous sampled miss:

1. **STRICT_SAME_CUTOFF:** source-visible declaration cutoff identical, and neither context has a temporary extension.
2. **ADVANCED_PREFIX_REFERENCES_VISIBLE:** cutoff increased, no temporary extension, and a capped walk of the expression's source DAG shows all *direct syntactic* constant/projection names had original declaration indices strictly below both cutoffs.
3. **ADVANCED_PREFIX_BLOCKED / UNKNOWN:** increased cutoff, but some direct name was not visible under the earlier cutoff, a declaration index was absent, or capped traversal was incomplete.
4. **REGRESSED_PREFIX / TEMP_CONTEXT:** cutoff decreased or a temporary environment extension was involved. Never treat these as reusable merely from expression identity.

Compute source-dependency support only on first observation of each sampled identity; bound traversal at 8,192 unique syntax nodes, reporting truncated/unknown cases without guessing. Record expression-head histograms and inclusive sampled `eval_no_cache` nanoseconds as **diagnostic cost hints**, not retired instructions or causal speedup. Report first misses and exact cache-hit counts separately.

## Frozen experiment boundary

- Checker: this isolated research branch, with unchanged proof-verdict code and an opt-in `reuse-scope-probe` Cargo feature depending on `reuse-probe`.
- Input: Lean Arena `b83254de5146ef34147ab82a48edbe1856b0edcc`, complete Mathlib 6,184,415,052 bytes, SHA-256 `22c5de83469408950005589a3bc5ef5157c65549b5a802f85d567c29151306a6`.
- Baseline: identical checkout compiled without probe features, 4 workers, same native JSON stdin configuration. Compare exact accepted stdout and successful exit codes; no other checker implementation may stand in as baseline.
- Run new RED→GREEN unit/CLI tests, the qualified 43 existing library tests, and retain both missing-fixture `should_panic` tests as unqualified, not proof rejections.
- Mutation controls: same expression + changed cutoff must not count as strict context; missing declaration identity or traversal cap cannot become supported; temporary extension must be excluded; missing or wrong probe record fails CI.
- Report peak RSS and wall/user times as operational observations, not performance benefit; reject scope instrumentation as too intrusive if peak RSS exceeds 1.15× the matched uninstrumented run.

## Predeclared readout gates

- If `ADVANCED_PREFIX_REFERENCES_VISIBLE >= 1,000` **and** at least 20% of cross-reset candidate events, proceed to independently proving/checking source-prefix support invariance and a cost-weighted persistent-node vertical slice. This classification alone does not certify transitive dependencies, universe/motive semantics, or safe lifetime transport.
- Otherwise, if `STRICT_SAME_CUTOFF >= 1,000` and at least 5% of cross-reset candidates, pursue only the narrower exact-context family.
- Otherwise reject this sampled identity-persistence route under the current representation and prioritize ROS's `check_against(expected)` typed-judgment vertical slice.
- Regardless of gate, no speedup or graph-native correctness is warranted until an actual safe reusable representation survives native full-Mathlib, mutation-negative acceptance, independent cost measurement, bounded lifetime memory, and a strong equivalent baseline.
