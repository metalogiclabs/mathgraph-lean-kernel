# V25 — Measurement / Experiment Genesis

## Question
Can the verified residual force synthesis of a useful measurement program from a lower-level anonymous interaction basis, rather than being handed a measurement operator or traversal vocabulary?

## Frozen setup
- Accepted G1 + G2 + G3 (`final_field_pi`) prefix is frozen.
- Discovery corpora: dependency-complete Std and Cedar prefixes through row 400000.
- Prospective transfer: rows 400001..600000, untouched during selection.
- Verifier label remains `safe := ptr::eq(struct_ty, force_all(depth, struct_ty))` at the projection site.
- Initial learner-visible state exposes only root discriminant, context depth, and generic Boolean facts (`spine_empty`, `closed`, `canonical`).
- No V23 traversal primitives, V24 presentation operators, slot family, direct nested-head source, semantic Rust variant name, or semantic field name is exposed.

## Residual-driven bounded measurement grammar
After the initial zero-unsafe frontier is shown insufficient, the learner may synthesize one anonymous experiment program from a generic interaction basis over the opaque root:

- `touch(root,0)` and `touch(root,1)` produce two anonymous interaction responses;
- `delta(a,b)`, `mix(a,b)`, and `identity(a)` are generic response combinators;
- `observe(expr)` converts one synthesized response program into an anonymous scalar measurement.

The learner is not told which response corresponds to a semantic field or why any response is useful. Candidate experiment programs compete under zero-unsafe coverage, then minimum description cost. The same frozen scalar transform grammar (`shr`, `and`, `mod`, `neq0`) and generic predicate grammar are used after measurement synthesis.

This is intentionally a bounded experiment-language test. Runtime instrumentation still implements the anonymous interaction responses from Rust structure; the claim is not arbitrary raw-memory reflection or unrestricted invention of physical sensors.

## Deciding gates
1. Both safe and unsafe discovery events occur.
2. Initial observation language frontier is strictly below the best synthesized-experiment frontier.
3. Exactly one best behavioural measurement class exists.
4. Exact measurement-program ablation removes every program in that behavioural class and strictly lowers the frontier.
5. At least one distractor experiment is observationally available but not in the winning behavioural class.
6. No V23/V24 traversal or measurement operator names, slot language, or semantic Rust field/variant names are exposed to the learner.
7. Frozen learned guard is byte-identical to G3 on Std and Cedar through row 400000.
8. Broadening learned predicate to `TRUE` fails or disagrees.
9. Same frozen experiment/measurement/guard is byte-identical to G3 through row 600000 on Std and Cedar.

## Classification
`MEASUREMENT_EXPERIMENT_GENESIS_V25=BOUNDED_POSITIVE` iff gates 1–9 pass. Otherwise retain `NO_GENESIS_NEEDED`, `UNDERIDENTIFIED`, `FALSIFIED`, or operational failure.

## Boundary
A positive result shows bounded residual-driven synthesis of a useful measurement program from a supplied anonymous interaction algebra. The remaining crutch is the generic interaction basis itself (`touch`, response combinators, `observe`) and the externally fixed verifier target.