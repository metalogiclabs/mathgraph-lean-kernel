# V24 — Cross-Presentation Traversal Genesis

## Question
Does the same verifier residual force two disjoint anonymous structural-interaction presentations to recover the same behavioural measurement class, even when their literal operator vocabulary and scalar encoding differ?

## Frozen base
- Parent is the verified V23 deciding commit `2467c0de9961628ed474a398936155e282cd8019`.
- Accepted G1 + G2 + G3 (`final_field_pi`) prefix is unchanged.
- Verifier label remains `safe := ptr::eq(struct_ty, force_all(depth, struct_ty))` at the same projection site.
- Discovery corpora remain dependency-complete Std and Cedar prefixes through row 400000.
- Prospective evaluation remains through row 600000; rows 400001..600000 are untouched during selection.
- Initial observation language remains root discriminant, generic facts (`spine_empty`, `closed`, `canonical`), and context depth.

## Two disjoint presentations
The learner receives the same anonymous event table but is evaluated under two independently named structural-interaction grammars.

Presentation A:
- `read(mark(root))`
- `read(next(mark(root)))`
- `read(root)` distractor

Presentation B:
- `sample(focus(root,zero))`
- `sample(focus(root,one))`
- `sample(root)` distractor

No token is shared between the generated A and B operator languages. Presentation B additionally applies a fixed reversible 64-bit presentation scrambling (rotation plus xor constant) to each scalar source before the frozen low-level bit-probe grammar is applied. Therefore literal selected source expressions/bit positions need not agree.

Neither presentation exposes V23's tokens `enter`, `advance`, or `emit_disc`, a combined decomposition operator, Rust variant names, or semantic field names.

For each generated scalar source the frozen low-level grammar remains bit tests built from `shr`, `and`, `mod`, `neq0`; predicates remain conjunctions over generic facts and generated Boolean `g`.

## Deciding gates
1. Both safe and unsafe discovery events occur.
2. The initial language is insufficient in both presentations.
3. Each presentation has exactly one best behavioural generated-operator class.
4. Each presentation strictly improves the zero-unsafe safe frontier over the initial language.
5. Exact per-presentation operator-class ablation collapses the best frontier below the selected frontier.
6. The best A and B solutions induce exactly the same Boolean measurement vector and exactly the same accepted-event predicate signature on all discovery events, despite disjoint syntax and scrambled B scalars.
7. No generated operator token is shared across presentations and no V23 traversal primitive or semantic name is exposed.
8. A frozen canonical guard extracted from the converged behavioural class is byte-identical to G3 on Std and Cedar through row 400000.
9. Broadening that guard to `TRUE` fails or disagrees on at least one discovery corpus.
10. The same frozen canonical guard is byte-identical to G3 on Std and Cedar through row 600000.

## Classification
`CROSS_PRESENTATION_TRAVERSAL_GENESIS_V24=BOUNDED_POSITIVE` iff gates 1–10 pass. Otherwise retain `NO_GENESIS_NEEDED`, `UNDERIDENTIFIED`, `PRESENTATION_DIVERGENCE`, or `FALSIFIED`.

## Boundary
A positive result is presentation-invariance evidence for the residual-selected behavioural measurement class. It does not establish autonomous invention of arbitrary raw-memory traversal primitives. Both presentations still come from supplied bounded structural-interaction grammars and the runtime instrumentation still knows the Rust structure used to generate anonymous event columns.
