# V12 — residual-driven applicability genesis

## Question
Can a previously overgeneralized kernel capability discover its own minimal applicability condition from verifier-governed experience, then transfer that condition to untouched workloads?

The motivating residual is the V10 Cedar failure of the broad `Value::Rigid => bypass force_all` projection optimization.

## Frozen substrate
The accepted G1 + G2 + G3(final_field_pi) prefix is unchanged.

The candidate capability is the projection `struct_ty` force bypass.

## Allowed learner information
For each projection event on the discovery prefixes the probe may expose only:

- an anonymous/local pre-force `RigidHead` tag (`bvar`, `axiom`, `ctor`, `recursor`, `quotconst`, `inductive`, or `nonrigid`), and
- whether `force_all` returned the identical semantic value (`std::ptr::eq(pre, post)`).

The learner is **not** supplied a rule saying that inductive heads are safe. It chooses the set of observed rigid-head tags for which every discovery event was unchanged by forcing.

This is a finite bounded condition language, not unrestricted concept formation.

## Discovery / held-out split
Discovery uses dependency-complete prefixes through row 400,000 of Std and Cedar. This intentionally includes the already-observed V10 residual region.

Prospective transfer uses the untouched continuation region rows 400,001..600,000, measured by dependency-complete prefix subtraction and exact replay at both boundaries.

## Frozen gates
1. Probe runs successfully on both discovery corpora.
2. At least one rigid-head tag is accepted and at least one is rejected.
3. Learned rule contains only tags with zero changed events in discovery.
4. **Exact ablation:** broaden the learned rule by one rejected observed tag. At least one discovery corpus must fail or disagree with the G3 baseline.
5. Learned guarded capability is byte-identical to G3 on Std and Cedar at both 400k and 600k boundaries.
6. Therefore rows 400001..600000 transfer with exact semantic preservation.
7. Callgrind window deltas are reported, but economic improvement is not required for the applicability-genesis claim.

## Classification
`APPLICABILITY_GENESIS_V12 = BOUNDED_POSITIVE` iff gates 1–6 pass.

A held-out semantic mismatch falsifies transfer of the learned applicability condition. No accepted/rejected split means the bounded learner is underidentified. Failure of the broadened ablation means minimality/causality is not demonstrated.
