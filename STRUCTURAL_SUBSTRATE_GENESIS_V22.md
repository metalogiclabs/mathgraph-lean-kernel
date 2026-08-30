# V22 — Structural Substrate Genesis

## Question
Can a verifier residual force a kernel-development system to introduce a new structural decomposition substrate, rather than merely selecting or defining a path inside a supplied cell interface?

## Frozen setup
- Accepted G1 + G2 + G3 (`final_field_pi`) prefix is frozen.
- Discovery corpora are dependency-complete Std and Cedar prefixes through row 400000.
- Prospective evaluation extends those same dependency-complete prefixes through row 600000; rows 400001..600000 are untouched during selection.
- The verifier label at the projection site is unchanged: `safe := ptr::eq(struct_ty, force_all(depth, struct_ty))`.
- Initial observation language has only generic facts (`spine_empty`, `closed`, `canonical`) plus root discriminant and context depth. It has no payload-cell sequence, no `slot(i)`, no `start/next/read`, and no direct nested-head observation.

## Residual-driven substrate expansion
When the initial zero-unsafe frontier is incomplete, the frozen expansion generator may add one anonymous structural substrate constructor. The decisive candidate is a generic active-variant payload decomposition: it exposes anonymous payload components of the current opaque local value as traversable scalar observations. Competing non-payload structural bundles are scored under the same transform/predicate grammar.

The learner sees anonymous substrate identifiers and numeric observation columns only. It is not told Rust variant names, semantic field names, or that any payload component corresponds to a rigid head.

For every exposed scalar source, the frozen V17 low-level observation grammar is reused: `shr`, `and`, `mod`, `neq0`, integer constants. Predicate language is conjunctions over generic facts and generated Boolean observation `g`.

Selection objective, lexicographically:
1. maximize safe coverage at zero unsafe coverage;
2. minimize substrate + source + observation-program + predicate description length;
3. quotient syntactic ties by their generated truth vectors / behavioural predicate signatures.

## Deciding gates
1. Both safe and unsafe discovery events occur.
2. Initial substrate frontier is strictly below the best generated-substrate frontier.
3. Exactly one best behavioural substrate class exists.
4. Exact substrate ablation: remove every constructor in the selected behavioural substrate class and rerun synthesis; best zero-unsafe frontier strictly falls.
5. No cell-sequence, slot-family, semantic Rust variant name, or semantic field name is exposed to the learner.
6. Generated guarded checker is byte-identical to frozen G3 on Std and Cedar through row 400000.
7. Broadening the learned guard predicate to `TRUE` fails or disagrees on at least one discovery corpus.
8. The same frozen substrate/source/program/predicate is byte-identical to G3 on Std and Cedar through row 600000.

## Classification
`STRUCTURAL_SUBSTRATE_GENESIS_V22=BOUNDED_POSITIVE` iff gates 1–8 pass.

Other outcomes are `NO_GENESIS_NEEDED`, `UNDERIDENTIFIED`, or `FALSIFIED` and are scientific outcomes, not targets for post-hoc repair.

## Boundary
A positive result establishes bounded residual-driven genesis of a structural decomposition substrate over a supplied generic decomposition meta-operation. It does **not** establish unrestricted reflection, arbitrary sensor invention, arbitrary memory-layout discovery, or ontology-free concept formation. The remaining crutch would be the decomposition meta-operation itself.
