# Contextual accessibility calculus V9

Frozen before any V9 pairwise benchmark outcome is observed.

## Residual from V8

V8 was prospectively correct on 3/4 candidates. The miss was `g3_param`: semantic equivalence held, but the same local capability-preservation move was +78,432 instructions on Std and -136,941 on Cedar. Therefore accessibility cost is not a property of K alone; it is conditioned on workload/corpus and continuation context.

## Refined first-order model

For corpus/workload mu, define a corpus-conditioned marginal accessibility cost delta_mu(K). For unseen pairwise compositions, the first-order prediction is

    delta_mu(K_i + K_j) ~= delta_mu(K_i) + delta_mu(K_j)

No pairwise interaction term is fitted because no V9 pair outcome has been observed.

V8 revealed marginals relative to the same frozen G3 baseline:

- param: Std +78,432; Cedar -136,941
- prior: Std -349,782; Cedar -481,304
- rigid: Std -25,574; Cedar -102,009

Thus preregistered pair predictions are:

| pair | predicted Std delta | predicted Cedar delta | decision |
|---|---:|---:|---|
| param_prior | -271,350 | -618,245 | PROMOTE |
| param_rigid | +52,858 | -238,950 | VETO |
| prior_rigid | -375,356 | -583,313 | PROMOTE |

A candidate is PROMOTE iff measured Callgrind instructions are strictly lower than G3 on both Std and Cedar and exact checker output remains byte-identical.

## Falsification

- Any semantic mismatch is a model failure.
- Any pair whose measured transfer decision differs from the frozen decision is a prospective miss.
- 3/3 supports the corpus-conditioned first-order accessibility calculus on this held-out pair family.
- Any miss demonstrates that pairwise interaction/context terms are required beyond independent corpus-conditioned marginals.

No prediction, threshold, candidate, or corpus is changed after V9 timing outcomes are observed.
