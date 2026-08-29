# V13 Generative Applicability Genesis — preregistration

## Question
Can the checker infer a semantically valid applicability predicate for a learned capability from verifier-governed residuals without being handed the `RigidHead` variant labels as the candidate condition language?

## Frozen starting point
V12 established that the projection-force bypass is valid on observed `Inductive` pre-force states and invalid on observed `Recursor` states, with exact held-out transfer under an explicitly supplied finite head-tag vocabulary. V13 removes that supplied symbolic vocabulary from the learner.

## Observation substrate
At the projection site, the probe emits only anonymous primitive binary/equality features mechanically obtainable from the runtime value before forcing. The learner is not given semantic names such as `inductive` or `recursor`, nor a menu of head variants. Features may include anonymous discriminants, spine-length predicates, pointer/equality relations, and bounded structural tests already executable at that site. Feature identities are opaque integers in the learning stage.

## Predicate generator
Starting from atomic anonymous features, enumerate conjunctions of literals in increasing description length up to a frozen small bound. A predicate is licensed only if:
1. it covers at least one observed safe event;
2. it covers zero observed unsafe events;
3. no strictly cheaper generated predicate has the same safe coverage and zero unsafe coverage.

Choose the unique minimum-description licensed predicate if one exists. If multiple inequivalent minimum predicates remain, V13 stops with `UNDERIDENTIFIED`; it must not choose using semantic names or source knowledge.

## Discovery / transfer split
Discovery: dependency-complete Std and Cedar prefixes through row 400000, identical to V12.
Prospective transfer: untouched rows 400001..600000.

## Deciding gates
1. Probe/build succeeds on both discovery corpora.
2. Both safe and unsafe projection events are observed.
3. The generated condition language contains a unique minimum licensed predicate, or the run reports `UNDERIDENTIFIED` rather than forcing a choice.
4. Exact broadening ablation: remove one literal or choose the nearest strictly broader generated predicate; at least one discovery corpus must fail or disagree with G3.
5. The learned generated guard is byte-identical to G3 on Std and Cedar at the 400k discovery boundary.
6. The same frozen predicate is byte-identical to G3 on Std and Cedar at the 600k boundary, hence exact on held-out rows 400001..600000.
7. Economic Callgrind deltas may be reported but are non-gating.

## Classification
`GENERATIVE_APPLICABILITY_V13=BOUNDED_POSITIVE` iff gates 1–6 pass without semantic-name leakage into the learner.
`GENERATIVE_APPLICABILITY_V13=UNDERIDENTIFIED` if the anonymous feature grammar cannot uniquely justify a predicate.
`GENERATIVE_APPLICABILITY_V13=FALSIFIED` if a uniquely learned predicate fails prospective semantic transfer.

## Boundary
This is still bounded predicate synthesis over mechanically supplied primitive runtime tests. It is stronger than V12 because the applicability condition is composed from anonymous primitives rather than selected from a supplied semantic tag vocabulary. It is not unrestricted representation-language genesis.