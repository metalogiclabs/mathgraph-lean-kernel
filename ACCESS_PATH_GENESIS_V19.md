# V19 — Access-Path Genesis

## Question
Can a verifier residual license construction of the runtime access path used by a learned applicability guard, rather than choosing among pre-extracted source channels?

## Frozen setup
Baseline is the accepted G1+G2+G3(final_field_pi) prefix. Discovery corpora are dependency-complete Std and Cedar prefixes through row 400000; prospective transfer extends to row 600000.

The learner starts with only the generic boolean facts `spine_empty`, `closed`, and `canonical`. It does not receive V18 channels `s0..s3` as named inputs.

A frozen bounded access-path grammar may construct observations from the local projection state using:
- root object: `struct_ty`
- conditional selector: `rigid.head`
- conditional selector: `rigid.spine`
- scalar context root: `depth`
- generic terminal observations: discriminant hash for runtime nodes, identity for scalar context
- generic arithmetic program grammar: `shr`, `and`, `mod`, `neq0` with small integer constants.

Concrete path spellings are scored only through their discovery-event behavioural vectors. Syntactic ties with the same behaviour collapse to one behavioural class. Inequivalent tied best classes imply UNDERIDENTIFIED.

## Objective
Lexicographic:
1. maximize verifier-safe coverage subject to zero unsafe coverage;
2. minimize total path + program + predicate description cost;
3. quotient remaining ties by behavioural truth vector.

## Deciding gates
1. Both safe and unsafe projection events exist.
2. Initial generic-fact language is strictly insufficient for the best safe frontier.
3. Exactly one best behavioural access-path+program class reaches the enlarged frontier.
4. Exact path ablation: remove every access path in the selected behavioural source class and rerun synthesis; the best safe frontier must strictly fall.
5. No semantic variant names are exposed to the learner.
6. Learned guard is byte-identical to G3 on Std and Cedar discovery prefixes.
7. A strictly broader guard fails or differs on at least one discovery corpus.
8. Frozen path/program/predicate is byte-identical to G3 on Std and Cedar through row 600000.

## Classification
`ACCESS_PATH_GENESIS_V19=BOUNDED_POSITIVE` iff gates 1–8 pass.
Otherwise classify as `NO_GENESIS_NEEDED`, `UNDERIDENTIFIED`, or `FALSIFIED` according to the failed scientific gate.

## Boundary
This is bounded access-path genesis inside a supplied generic selector/observer grammar. It is not unrestricted invention of the selector grammar, observation site, or arbitrary source-code instrumentation.