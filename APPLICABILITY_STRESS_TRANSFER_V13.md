# V13 — Full-corpus applicability stress transfer

## Frozen source result

V12 learned the projection bypass applicability rule `Gamma = {inductive}` from dependency-complete Std+Cedar prefixes through row 400000. It rejected `recursor`; broadening the rule to include `recursor` reproduced the semantic failure. V12 then transferred byte-identically through row 600000 on both corpora.

## Prospective question

Does the V12 rule remain semantically valid over the entire available real Lean exports, and do new pre-force head classes appear that expose an underidentified applicability boundary?

## Frozen rule

No relearning is allowed in V13.

`Gamma_V12 = {inductive}`.

All other pre-force classes remain outside the bypass region, including classes unseen during V12 discovery.

## Test corpora

Use the complete Lean Kernel Arena exports generated in the V13 run:

- Std: entire `std.ndjson` export (~10.0M lines)
- Cedar: entire `cedar.ndjson` export (~14.6M lines)

These extend far beyond both the V12 discovery prefix (<=400000) and V12 held-out transfer prefix (<=600000).

## Gates

1. Reconstruct the frozen accepted G1+G2+G3(final_field_pi) prefix.
2. Instrument a probe that records the pre-force projection-type head class and whether `force_all` returns the identical value pointer.
3. Apply the frozen V12 guard exactly: bypass only `RigidHead::Inductive`; force every other class.
4. Require byte-identical checker output between G3 and guarded V13 on the full Std export.
5. Require byte-identical checker output between G3 and guarded V13 on the full Cedar export.
6. Require every observed `inductive` probe event to be unchanged by forcing. Any changed `inductive` event falsifies the learned applicability rule.
7. Report all newly observed head classes and their changed/unchanged counts. They do not expand Gamma in this run.

## Classification

`APPLICABILITY_STRESS_TRANSFER_V13 = BOUNDED_POSITIVE` iff both full corpora are byte-identical under the frozen guard and all observed `inductive` events remain unchanged.

Any semantic mismatch or any changed `inductive` event => `FALSIFIED_OR_INCOMPLETE`.

Operational build/infrastructure failure => `UNTESTED`.

## Scientific boundary

A positive result supports transfer of one learned applicability predicate across two much larger real Lean workloads. It does not establish universal Lean validity, minimality over unobserved feature languages, or economic value. No performance claim is gated in V13.