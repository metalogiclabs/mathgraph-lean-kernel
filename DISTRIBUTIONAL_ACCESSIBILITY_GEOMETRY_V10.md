# Distributional accessibility geometry V10

This document freezes predictions before any V10 benchmark outcome is observed.

## Residual carried forward

V8 falsified a context-free marginal accessibility model: `param` was harmful on Std but beneficial on Cedar. V9 falsified corpus-conditioned additivity: `param+rigid` was predicted VETO on Std but actually PROMOTE. The remaining live hypothesis is that accessibility cost is conditional on both workload distribution and the retained capability set:

`d_G(c | mu, kappa, K_t)`.

## Frozen training evidence

All values below were observed only on the first 100,000 records of each corpus.

Decisions relative to the accepted G1+G2+G3 baseline:

| subset | frozen first-slice decision |
|---|---|
| `param` | VETO (Std positive delta, Cedar negative delta) |
| `prior` | PROMOTE |
| `rigid` | PROMOTE |
| `param_prior` | PROMOTE |
| `param_rigid` | PROMOTE |
| `prior_rigid` | PROMOTE |
| `all` | PROMOTE |

The full lattice therefore contains a state-dependent sign reversal: `param` alone is vetoed, while `param+rigid` and `param+prior` are promoted.

## Prospective distribution-shift test

V10 does not reuse the first 100k rows. It opens distant, previously unbenchmarked slices:

- Std rows 5,000,001 through 5,100,000.
- Cedar rows 10,000,001 through 10,100,000.

The frozen prediction is that the *decision topology* transfers even if magnitudes change:

- `param` remains VETO because it is non-positive on at least one corpus.
- every other non-empty subset remains PROMOTE on both corpora.
- exact checker output remains byte-identical for every state.

A single decision mismatch falsifies distributional transfer of the learned accessibility geometry. If the seven decisions all match, this is evidence that the state-dependent capability geometry is not an artifact of the first 100k-row sample.

No prediction or threshold may be changed after V10 outcomes are observed.
