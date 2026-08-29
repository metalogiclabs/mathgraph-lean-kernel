# V15 Probe-Form Genesis — preregistration

## Question
Can a verifier residual force synthesis of the *form* of a new observation probe from a smaller generic operator alphabet, rather than selecting from a pre-supplied family of discriminant-bit probes?

## Frozen starting point
V14 established that the initial basis `spine-empty`, `closed`, `canonical` reaches only 49/167 safe projection events, while a newly added anonymous discriminant-derived probe expands the exact safe frontier to 167/167. V15 removes the fixed family `bit_k(hash(discriminant(head)))` as a menu.

The learner starts only with the same three generic basis facts and a generic expression grammar over anonymous runtime atoms:

- source atoms: `disc_hash(head)`, `spine_len`, `is_closed`, `is_canonical`;
- constants: small unsigned integers 0..15;
- unary operators: `bit(x,k)`, `eq(x,k)`, `neq(x,k)`;
- binary operators: `and`, `or`;
- bounded expression cost <= 4.

No `RigidHead` semantic variant names are available to synthesis or deployment. The verifier label remains pointer preservation under the original `force_all`; the label is never available to the deployed guard.

## Residual-driven synthesis
1. Measure the zero-unsafe safe frontier using only the original three basis facts.
2. If that basis already reaches all safe events, classify `NO_GENESIS_NEEDED`.
3. Otherwise enumerate the frozen expression grammar by increasing cost and evaluate generated probe expressions extensionally on the discovery corpus.
4. Collapse extensionally identical generated probes into behavioural classes.
5. Select the unique minimum-cost behavioural probe class that maximally increases zero-unsafe safe coverage.
6. Adjoin only that generated probe and synthesize the minimum zero-unsafe guard.

Ties between inequivalent minimum behavioural classes yield `UNDERIDENTIFIED`.

## Discovery / transfer split
Discovery: dependency-complete Std+Cedar prefixes through row 400000.
Prospective transfer: rows 400001..600000 through dependency-complete 600000-row prefixes.

## Deciding gates
1. Both safe and unsafe discovery events occur.
2. Initial observation basis is strictly insufficient.
3. Generated expression search produces a strict frontier expansion.
4. A unique minimum behavioural probe class is selected.
5. Probe expression is serialized from the generic grammar derivation rather than selected from a fixed discriminant-bit menu.
6. Exact probe ablation restores the initial frontier.
7. Exact predicate broadening fails or disagrees with G3 on at least one discovery corpus.
8. Learned guard is byte-identical to G3 on Std+Cedar at 400k.
9. Frozen generated probe and guard remain byte-identical to G3 on Std+Cedar at 600k.

## Classification
- `PROBE_FORM_GENESIS_V15=BOUNDED_POSITIVE` iff gates 1–9 pass.
- `PROBE_FORM_GENESIS_V15=NO_GENESIS_NEEDED` if the original basis suffices.
- `PROBE_FORM_GENESIS_V15=UNDERIDENTIFIED` if multiple inequivalent minimum generated probe classes remain.
- `PROBE_FORM_GENESIS_V15=FALSIFIED` if a uniquely selected generated probe fails exact discovery semantics or prospective transfer.

## Boundary
This remains bounded program synthesis over a supplied generic operator alphabet. It does not establish unrestricted invention of primitive operators or autonomous creation of the grammar itself.

<!-- trigger: neutral CI instantiation commit; scientific specification unchanged -->
