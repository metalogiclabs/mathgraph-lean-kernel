# V20 — Access-path grammar genesis

## Question
Can a verifier residual demonstrate that the current access-path grammar is insufficient, license the smallest new anonymous selector production, and use that grammar extension to synthesize a prospectively valid applicability guard?

## Frozen starting point
The accepted G1+G2+G3(final_field_pi) prefix is unchanged.

The **initial path grammar** can observe only:
- `root.disc`
- `root.rigid.spine.disc`
- `context.depth`

It cannot select another field of the local rigid record. The generic facts `spine_empty`, `closed`, and `canonical` remain available to the predicate layer.

## Frozen grammar-extension generator
The only developmental action is to adjoin one anonymous generic selector production

`slot(i)` for `i in {0,1}`

at the local rigid record, followed by the already available generic `disc` observation. The learner receives only anonymous slot indices and verifier outcomes; it is not told semantic variant names. `slot(0)` and `slot(1)` are treated as generated grammar productions, not as pre-existing paths. Syntactically different candidates are quotiented by their truth vector on discovery events before uniqueness is judged.

This is deliberately a **bounded grammar-genesis** experiment. The selector meta-generator `slot(i)` is supplied; unrestricted invention of selector meta-grammar is not claimed.

## Objective
For a condition language, maximize safe-event coverage subject to zero unsafe coverage; then minimize description cost; then quotient ties by behavioural truth vector.

A genuine grammar residual exists only if the best initial-grammar frontier is strictly smaller than the best frontier after adjoining one generated selector production.

## Discovery and transfer
Discovery: dependency-complete Std and Cedar prefixes through row 400000.
Prospective transfer: untouched prefixes through row 600000; the held-out region is rows 400001..600000.

## Deciding gates
1. Probe succeeds and observes both verifier-safe and verifier-unsafe events.
2. Initial grammar frontier is measured before generated selectors are admitted.
3. Adding exactly one generated selector production strictly increases zero-unsafe safe coverage.
4. Exactly one best behavioural selector+program class exists at the enlarged frontier; inequivalent ties are `UNDERIDENTIFIED`.
5. Exact selector-production ablation removes the selected production and restores a strictly smaller reachable frontier.
6. Deliberately broadening the synthesized guard causes failure or output disagreement on at least one discovery corpus.
7. Generated guard is byte-identical to G3 on Std and Cedar through row 400000.
8. The same frozen grammar extension, path program, and guard are byte-identical through row 600000 on both corpora.

## Classification
`ACCESS_PATH_GRAMMAR_GENESIS_V20=BOUNDED_POSITIVE` iff gates 1–8 pass.

Other terminal classifications:
- `NO_GENESIS_NEEDED`: initial grammar already reaches the maximal safe frontier.
- `UNDERIDENTIFIED`: multiple inequivalent best grammar extensions remain.
- `FALSIFIED`: generated extension fails strict gain or prospective exactness.

## Claim boundary
A positive result supports verifier-governed **bounded access-path grammar extension**. It does not establish unrestricted invention of observation primitives, selector meta-grammars, or ontology.