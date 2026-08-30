# V23 — Decomposition Operator Genesis

## Question
Can a verifier residual force synthesis of the structural decomposition operator itself from lower-level anonymous traversal primitives, rather than selecting a supplied decomposition substrate?

## Frozen setup
- Accepted G1 + G2 + G3 (`final_field_pi`) prefix is frozen.
- Discovery corpora are dependency-complete Std and Cedar prefixes through row 400000.
- Prospective evaluation extends through row 600000; rows 400001..600000 remain untouched during selection.
- Verifier label remains `safe := ptr::eq(struct_ty, force_all(depth, struct_ty))` at the projection site.
- Initial observation language exposes only root discriminant, generic facts (`spine_empty`, `closed`, `canonical`), and context depth.
- No payload decomposition operator, payload-cell sequence, slot family, field name, or direct nested-head observation is present initially.

## Residual-driven operator genesis
When the initial zero-unsafe frontier is incomplete, a bounded generic operator grammar becomes available over an opaque active-value cursor:
- `enter(root)` — enter the anonymous active payload cursor;
- `advance(cursor)` — move one anonymous payload position;
- `emit_disc(cursor)` — emit the discriminant hash of the currently selected anonymous component.

The learner must synthesize a composition of these primitives. The grammar contains no Rust variant names or semantic field names. Competing operator programs are scored by the same zero-unsafe coverage / minimum-description objective.

For each generated scalar source the frozen low-level observation grammar remains `shr`, `and`, `mod`, `neq0` plus integer constants; predicate language remains conjunctions over generic facts and generated Boolean `g`.

## Deciding gates
1. Both safe and unsafe discovery events occur.
2. Initial operator language frontier is strictly below the best generated-operator frontier.
3. Exactly one best behavioural decomposition-operator class exists.
4. Exact operator-definition ablation: remove all programs in that behavioural class; best zero-unsafe frontier strictly falls.
5. No combined decomposition operator, cell sequence, slot family, semantic Rust variant name, or semantic field name is exposed to the learner.
6. Generated guarded checker is byte-identical to frozen G3 on Std and Cedar through row 400000.
7. Broadening the learned predicate to `TRUE` fails or disagrees on at least one discovery corpus.
8. The same frozen operator/source/program/predicate is byte-identical to G3 on Std and Cedar through row 600000.

## Classification
`DECOMPOSITION_OPERATOR_GENESIS_V23=BOUNDED_POSITIVE` iff gates 1–8 pass. Otherwise `NO_GENESIS_NEEDED`, `UNDERIDENTIFIED`, or `FALSIFIED` is retained as the scientific result.

## Boundary
A positive result establishes bounded synthesis of a useful decomposition operator from a supplied anonymous traversal-combinator language. It does not establish unrestricted reflection, arbitrary pointer arithmetic, raw memory-layout invention, or autonomous invention of the traversal primitives themselves. The remaining crutch would be the primitive traversal alphabet `enter/advance/emit_disc`.
