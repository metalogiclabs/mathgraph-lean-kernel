# V16 Operator-Alphabet Genesis — preregistration

## Question
Can a verifier residual justify adding a new *operator schema* to an initially insufficient observation grammar, rather than merely selecting a probe expression from operators already supplied?

## Frozen starting point
The real checker target, accepted G1+G2+G3 prefix, discovery corpora, verifier label, and prospective split are unchanged from V15.

The learner initially receives only:

- raw anonymous `disc_hash(head)` as an unsigned integer;
- `spine_empty`, `closed`, `canonical`;
- Boolean conjunction;
- equality / inequality of `disc_hash` against small constants 0..15.

The initial language does **not** contain bit extraction, shifts, masks, modulo, `RigidHead` names, or any semantic enum labels.

## Residual-licensed grammar expansion
If the initial grammar is insufficient, one operator schema may be adjoined from a frozen, generic integer-transformation meta-family:

- `shift_mask(x,k) := (x >> k) & 1`
- `shift_mod2(x,k) := (x >> k) % 2`
- `mask_nonzero(x,k) := 1[(x & (1 << k)) != 0]`

with k in 0..15. These schemas are mechanically parameterized integer operations; they do not name any Lean semantic variant. Extensionally identical candidates are collapsed into behavioural classes before selection.

The scientific object is the selected **behavioural operator class**, not a preferred spelling. A unique best behavioural class is required.

## Selection
1. Measure the maximum zero-unsafe safe frontier under the initial grammar.
2. If it already covers all safe events, classify `NO_GENESIS_NEEDED`.
3. Evaluate every generated operator-schema instance on the discovery residuals.
4. For each instance, adjoin its Boolean output `g` and synthesize the minimum zero-unsafe conjunction over the original generic facts plus `g`.
5. Select maximum safe coverage, then minimum total description cost; collapse extensionally identical winners.
6. Multiple inequivalent best behavioural classes => `UNDERIDENTIFIED`.

## Discovery / transfer split
Discovery: dependency-complete Std+Cedar prefixes through row 400000.
Prospective transfer: rows 400001..600000 through dependency-complete 600000-row prefixes.

## Deciding gates
1. Both safe and unsafe discovery events occur.
2. Initial grammar is strictly insufficient.
3. Residual-licensed operator expansion gives strict frontier gain.
4. Unique best behavioural operator class.
5. No semantic variant names exposed to learner/deployment.
6. Exact operator ablation restores the initial frontier.
7. Generated guard is byte-identical to G3 on Std+Cedar at 400k.
8. Weakening generated guard to `TRUE` fails or disagrees with G3 on at least one discovery corpus.
9. Frozen generated operator and guard remain byte-identical to G3 on Std+Cedar at 600k.

## Classification
- `OPERATOR_ALPHABET_GENESIS_V16=BOUNDED_POSITIVE` iff gates 1–9 pass.
- `NO_GENESIS_NEEDED` if the initial grammar suffices.
- `UNDERIDENTIFIED` if multiple inequivalent best operator classes remain.
- `FALSIFIED` if the selected operator/guard fails exact discovery semantics or prospective transfer.

## Boundary
This is bounded operator-schema genesis from a supplied generic integer meta-family. It does **not** establish unrestricted invention of primitive operators, autonomous invention of the meta-family, or open-ended concept formation.