# V24 — Traversal Primitive Genesis

## Question
Can a verifier residual force synthesis of a useful structural observation primitive itself from a lower-level anonymous micro-machine, rather than composing a supplied traversal alphabet such as `enter/advance/emit_disc`?

## Frozen setup
- Accepted G1 + G2 + G3 (`final_field_pi`) prefix is frozen.
- Discovery corpora are dependency-complete Std and Cedar prefixes through row 400000.
- Prospective evaluation extends through row 600000; rows 400001..600000 remain untouched during selection.
- Verifier label remains `safe := ptr::eq(struct_ty, force_all(depth, struct_ty))` at the projection site.
- Initial observation language exposes only root discriminant, generic facts (`spine_empty`, `closed`, `canonical`), and context depth.
- No payload decomposition operator, cell sequence, slot family, nested-head observation, or named traversal primitive (`enter`, `advance`, `emit_disc`) is available to the learner.

## Residual-driven primitive genesis
When the initial zero-unsafe frontier is incomplete, the frozen generator exposes only an anonymous two-instruction micro-machine:
- `touch(root, i)` returns an opaque local handle for anonymous opcode `i`;
- `sense(handle, j)` emits an anonymous scalar for opcode `j`.

The learner is not told what any opcode means. It synthesizes a primitive program by composing these generic micro-ops. The frozen candidate programs are equal-budget compositions over the bounded opcode set and include distractors. They carry no Rust variant names, field names, payload-position names, or traversal-semantic labels.

For every synthesized scalar primitive, the frozen low-level observation grammar remains `shr`, `and`, `mod`, `neq0` plus integer constants; predicate language remains conjunctions over generic facts and generated Boolean `g`.

Selection objective, lexicographically:
1. maximize safe coverage at zero unsafe coverage;
2. minimize primitive-program + observation-program + predicate description length;
3. quotient syntactic ties by generated truth vector / behavioural predicate signature.

## Deciding gates
1. Both safe and unsafe discovery events occur.
2. Initial primitive language frontier is strictly below the best generated-primitive frontier.
3. Exactly one best behavioural primitive-definition class exists.
4. Exact primitive-definition ablation: remove every candidate in the selected behavioural class and rerun synthesis; best zero-unsafe frontier strictly falls.
5. No named traversal alphabet, combined decomposition operator, cell sequence, slot family, semantic Rust variant name, or semantic field name is exposed to the learner.
6. Generated guarded checker is byte-identical to frozen G3 on Std and Cedar through row 400000.
7. Broadening the learned predicate to `TRUE` fails or disagrees on at least one discovery corpus.
8. The same frozen primitive/source/program/predicate is byte-identical to G3 on Std and Cedar through row 600000.

## Classification
`TRAVERSAL_PRIMITIVE_GENESIS_V24=BOUNDED_POSITIVE` iff gates 1–8 pass. Otherwise `NO_GENESIS_NEEDED`, `UNDERIDENTIFIED`, or `FALSIFIED` is retained as the scientific result.

## Boundary
A positive result establishes bounded synthesis of a useful structural observation primitive from a supplied finite anonymous micro-machine. It does **not** establish unrestricted reflection, arbitrary pointer arithmetic, raw memory-layout invention, unrestricted instruction-set invention, or autonomous generation of the micro-machine itself. The remaining crutch would be the finite `touch/sense` meta-generator and its opcode space.
