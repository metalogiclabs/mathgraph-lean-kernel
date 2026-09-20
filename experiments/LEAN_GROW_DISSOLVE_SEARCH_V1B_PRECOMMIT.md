# LEAN GROW–DISSOLVE SEARCH V1B — selected-action measurement recovery

Status: **FROZEN BEFORE IMPLEMENTATION OR OUTCOME EXECUTION**

## Parent authority

This follow-up does not reopen the developmental result from run 35524257419 / job 106113555314.

That parent run established, before the hardware-counter failure:

- developmental replay: PASS;
- 13-event past compressed into a 10-event held-out future stream;
- all protected future Flash decisions matched full-history replay;
- raw prefix bytes 3895;
- dissolved active-state bytes 1804;
- full-history replay work 185 abstract units;
- dissolved update work 110 units;
- final selected action: measure_ordinary_unfold_instructions;
- full pinned Lean Kernel Arena parity: 409/409, 0 semantic mismatches;
- selected ordinary-Unfold candidate Mathlib exit-status parity: PASS.

The parent job then failed at the first hosted-runner command:

    perf stat -e instructions ...

before any instruction count was obtained.

This V1B is only a measurement-recovery experiment for that already-selected action.

## Governing question

Can the selected ordinary-Unfold candidate be evaluated on the hosted runner using alternative measurements without pretending those alternatives are the Arena's official hardware-instruction ranking metric?

The discipline is:

\[
\boxed{\text{recover evidence without changing the question or inflating the claim}}
\]

## Frozen source state

Base source is this branch, inherited from experiment/lean-grow-dissolve-search-v1.

Candidate source differs by exactly one frozen mutation:

    ORDINARY_UNFOLD_NEUTRAL: false -> true

No other source change is permitted.

## Build regime

Both base and candidate are built independently with the same exact native PGO procedure:

1. profile-generate build;
2. run init-prelude;
3. merge LLVM profile;
4. profile-use rebuild.

## Measurements

### M1. Explicit hardware-counter probe

Run a visible, non-suppressed:

    perf stat -e instructions true

and record stdout/stderr/exit code.

This diagnoses the hosted runner capability. Failure is a harness fact, not candidate evidence.

### M2. Mathlib status parity

Run base and candidate on the pinned Mathlib export.

Require equal exit status before any performance interpretation.

### M3. Alternating wall-time diagnostic

Run 5 alternating same-runner Mathlib A/B repetitions.

Report:

- all raw wall times;
- median base wall time;
- median candidate wall time;
- candidate/base speed ratio.

This is diagnostic only and is not the Arena ranking metric.

### M4. Deterministic Callgrind proxy

Run one Callgrind execution per arm on the exact same pinned Mathlib export under the same deterministic x86-64 PGO build regime.

Report:

- base Callgrind Ir;
- candidate Callgrind Ir;
- proxy ratio and delta.

Callgrind Ir is a deterministic instruction-execution proxy, not the official Arena hardware counter.

If either Callgrind run exceeds the frozen timeout, report PROXY_UNAVAILABLE rather than substituting another metric.

## Frozen gates

MR1. Parent run identity is recorded exactly.

MR2. Candidate diff is exactly the one ordinary-Unfold boolean toggle.

MR3. Base and candidate use identical PGO regimes.

MR4. Hardware-counter probe result is recorded with stderr and exit code.

MR5. Mathlib base/candidate exit-status parity holds.

MR6. Five alternating wall-time repetitions complete.

MR7. Wall-time result is reported descriptively and is not labeled Arena-rank authority.

MR8. Callgrind base/candidate result is reported if both complete; otherwise proxy unavailability is explicit.

MR9. Any Callgrind result is labeled a proxy, not official Arena instruction count.

MR10. No performance outcome can retroactively invalidate the already-established developmental equivalence result.

## Verdict vocabulary

- PASS_SELECTED_ACTION_MEASUREMENT_RECOVERY_V1B
- PARTIAL_SELECTED_ACTION_MEASUREMENT_RECOVERY_V1B
- VALID_NEGATIVE_SELECTED_ACTION_MEASUREMENT_RECOVERY_V1B

PASS means MR1–MR10 are all satisfied. Candidate performance itself may be positive or negative.

## Claim boundary

This experiment can recover a diagnostic and deterministic proxy for the selected action on a hosted runner. It cannot replace the official Arena hardware-instruction metric unless that hardware counter becomes available.
