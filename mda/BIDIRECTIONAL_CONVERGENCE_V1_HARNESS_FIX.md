# Harness fix — MDA bidirectional convergence v1

The first hosted run exposed a harness-only path bug before any candidate was evaluated.

## Failure

The ground-preparation job wrote `SHA256SUMS` using absolute paths under:

`/tmp/mda-bidir-ground-v1/tests/`

The matrix jobs downloaded the exact same frozen artifact under:

`/tmp/mda-bidir-ground/`

so `sha256sum -c SHA256SUMS` failed before running genesis or solvent.

## Correction

Generate `SHA256SUMS` from inside the artifact directory so it contains relative file names.

This changes neither:

- capability atoms;
- mask set;
- genesis construction rule;
- solvent construction rule;
- Arena pin;
- protected semantic outcomes;
- convergence criterion.

No candidate result from the failed run was observed because candidate execution never began.
