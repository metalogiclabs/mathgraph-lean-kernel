# V17 — Operator-definition genesis

## Question
Can a verifier residual force synthesis of a new applicability observation *definition* from lower-level anonymous primitives, rather than selecting from a menu of named operator schemas?

## Frozen setup
- Preserve the accepted G1+G2+G3 prefix.
- Discovery corpora: dependency-complete first 400,000 rows of Arena Std and Cedar.
- Prospective transfer: first 600,000 rows, with rows 400001..600000 untouched during synthesis.
- Learner sees only anonymous `disc_hash`, `spine_empty`, `closed`, `canonical`, and verifier label `safe := ptr_eq(pre_force, force_all(pre_force))`.
- No `RigidHead` semantic variant names are exposed.

## Initial language
The initial guard language may use `spine_empty`, `closed`, `canonical`, and direct equality/inequality comparisons on the raw anonymous hash. It has no shift, mask, modulo, or bit-extraction operation.

## Residual-driven definition grammar
Only if the initial language is insufficient, synthesize observation programs from the lower-level primitives:
- `shr(x,k)` for k in 0..15
- `and(x,1)`
- `mod(x,2)`
- `neq0(x)`

Programs are enumerated compositionally up to frozen cost/depth. There is no named menu such as `shift_mask`, `shift_mod2`, or `mask_nonzero`. Syntactically different programs with identical outputs and identical induced guards collapse into one behavioural class.

## Gates
1. Both safe and unsafe discovery events exist.
2. Initial language is insufficient for the full zero-unsafe safe frontier.
3. A generated program strictly expands that frontier.
4. The best minimum-cost generated solution is one behavioural class.
5. Exact program ablation restores the smaller initial frontier.
6. Semantic names are absent from learner inputs.
7. Compiled generated guard is byte-identical to G3 on Std and Cedar discovery prefixes.
8. Broadening the generated guard causes failure or output disagreement on at least one discovery corpus.
9. Frozen generated program and predicate remain byte-identical to G3 through 600,000 rows on both Std and Cedar.

## Classification
`OPERATOR_DEFINITION_GENESIS_V17=BOUNDED_POSITIVE` iff gates 1–9 pass. Otherwise classify as `FALSIFIED`, `UNDERIDENTIFIED`, or `NO_GENESIS_NEEDED` according to the first failed scientific condition.

## Boundary
This remains bounded synthesis from a supplied low-level primitive grammar. It is not unrestricted invention of computational primitives.