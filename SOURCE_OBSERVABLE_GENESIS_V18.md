# V18 — Source-observable genesis

## Question
Can the verifier residual discover *which local runtime state must be observed*, rather than receiving `disc_hash` as the designated raw input?

## Frozen setup
Baseline is the accepted G1+G2+G3(final_field_pi) prefix used in V12–V17. Discovery uses dependency-complete Std and Cedar prefixes through row 400000; prospective transfer uses prefixes through row 600000, with rows 400001..600000 untouched during selection.

The initial predicate language contains only three generic facts: spine-empty, closed, canonical, plus equality/inequality against small constants. It has no anonymous raw source channels.

During residual diagnosis the probe exposes four anonymous u64 channels, named only `s0..s3` to the learner:
- one channel derived from the outer `Value` discriminant,
- one from a nested rigid-head discriminant,
- one from the spine discriminant,
- one from the local depth.

The learner is not told which source is which. For each source it may synthesize only programs from the frozen low-level grammar used in V17: `shr`, `and`, `mod`, `neq0`, integer constants, and the anonymous source terminal.

## Objective
Lexicographic:
1. maximize verifier-safe event coverage subject to zero unsafe coverage;
2. minimize total source+program+predicate description length;
3. quotient syntactic ties by the generated truth vector on all discovery events.

## Deciding gates
1. Safe and unsafe events are both observed.
2. Initial no-source frontier is measured first and is strictly below the best source/program frontier.
3. Exactly one best behavioural source/program class remains after quotienting equivalent spellings.
4. **Exact source ablation:** remove every source channel belonging to the selected behavioural source class and rerun synthesis; the best zero-unsafe frontier must strictly fall.
5. No semantic Rust variant names are exposed to the learner.
6. Generated guard is byte-identical to G3 on Std and Cedar at row 400000.
7. Broadening the learned predicate to TRUE fails or disagrees on at least one discovery corpus.
8. The same frozen source/program/predicate is byte-identical to G3 on Std and Cedar through row 600000.

## Classification
`SOURCE_OBSERVABLE_GENESIS_V18=BOUNDED_POSITIVE` iff all gates pass.
`NO_GENESIS_NEEDED` if the initial language already reaches the full safe frontier.
`UNDERIDENTIFIED` if inequivalent best source/program classes remain or source ablation does not reduce the frontier.
`FALSIFIED` if the selected rule fails exact discovery or prospective transfer.

## Boundary
This is bounded source-selection genesis over a supplied anonymous local-source generator. It does not claim unrestricted invention of arbitrary measurements, source-path grammars, or new sensor modalities.