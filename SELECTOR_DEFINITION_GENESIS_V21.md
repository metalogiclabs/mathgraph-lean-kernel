# V21 — Selector-Definition Genesis

## Question
Can the verifier residual force the system to synthesize the **definition of a structural selector operation** from lower-level anonymous cursor primitives, rather than receiving a `slot(i)` selector family?

## Frozen setup
V21 inherits the accepted G1+G2+G3(final-field-pi) prefix and the same dependency-complete Std/Cedar discovery prefixes through row 400000. Prospective evaluation uses rows through 600000; rows 400001..600000 are untouched during synthesis.

The initial observation language contains only generic facts (`spine_empty`, `closed`, `canonical`) and paths available before the missing rigid-field selector (`root.disc`, `root.rigid.spine.disc`, `context.depth`). It cannot address the consequential nested field.

When the verifier residual demonstrates insufficiency, the expansion substrate is not a `slot(i)` menu. Instead the local rigid record is exposed as an anonymous finite cell sequence and the learner receives only the generic cursor primitives:

- `start(cells)` — cursor at the first anonymous cell;
- `next(cursor)` — advance one cell;
- `read(cursor)` — read the current anonymous cell value.

The learner synthesizes selector programs compositionally from these primitives, with at most one `next` in this frozen finite experiment. The two generated selector definitions are therefore not named or indexed slots; they are programs `read(start(cells))` and `read(next(start(cells)))` generated from the primitive grammar.

The observation transform grammar remains frozen from V17–V20: `shr`, `and`, `mod`, `neq0`, integer constants. Predicate search remains at most two literals over generic facts plus the generated bit.

## Deciding gates
1. Both safe and unsafe projection events occur.
2. The initial language's best zero-unsafe safe frontier is strictly below the best generated selector-definition frontier.
3. Exactly one best **behavioural selector-definition + observation-program class** exists under the frozen objective: maximize safe coverage at zero unsafe, then minimize description length.
4. **Exact selector-definition ablation:** remove every selector program in the selected behavioural class while leaving the same low-level cursor primitives and all other generated programs available; the best zero-unsafe frontier must strictly fall.
5. The learner receives no Rust semantic variant names and no `slot(i)` selector family.
6. The synthesized guard is byte-identical to the G3 reference on Std and Cedar through row 400000.
7. Broadening the learned predicate to TRUE must fail or disagree with G3 on at least one discovery corpus.
8. The frozen selector definition, observation program and predicate are byte-identical to G3 on Std and Cedar through row 600000, giving prospective transfer on untouched rows 400001..600000.

## Classification
`SELECTOR_DEFINITION_GENESIS_V21=BOUNDED_POSITIVE` iff gates 1–8 pass.

Alternative classifications are `NO_GENESIS_NEEDED`, `UNDERIDENTIFIED`, and `FALSIFIED`; they are scientific outcomes and must not be patched away.

## Claim boundary
A positive result establishes bounded synthesis of a selector **definition** from an anonymous finite-cell/cursor substrate. It does **not** establish unrestricted reflection, arbitrary memory traversal, automatic invention of the cell-sequence representation, or ontology-free measurement genesis. The remaining crutch would be the supplied anonymous structural decomposition into `cells` and the cursor meta-grammar itself.
