# Flash continuation — complete-input evidence reconciliation

The strongest current candidate is the attributed upstream-core reconciliation
at `bc704eebed4e009bc66af1a849f18315c11f1926` (source tree
`06c257f0f2ff1f64711cfa54620b650e6dd59b7e`). It integrates
Jeremy Chen's Apache-2.0 sokonanoda source at
`9a021b66f804a1d1df68a981337c67413ef72f6b` with MathGraph source-correspondence
checks and compatibility repairs. This is an attributed integration, not a new
independently authored kernel. Copyright and licence notices remain required.

## Warranted execution boundary

- Complete unchanged Mathlib: both baseline and strict candidate accepted all
  739,167 declarations in two alternating native rounds. Exact input: 6,326,141,213
  bytes, SHA-256 `f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec`.
- Median CPU 245.195 s -> 164.685 s: **32.8351% reduction**. Maximum observed
  peak RSS 6,491,968 KiB -> 4,872,228 KiB: **24.9499% reduction**. These are
  bounded native measurements, not retired instructions, statistical generality
  or an Arena score. Do not scale the published Arena time by this CPU ratio.
- 230 portable prescribed outcomes and 16 additional source-correspondence
  controls passed. Eight additional exact complete large-input accepts were
  independently checked. Alongside complete Mathlib, **239/240 prescribed
  outcomes** are evidenced. Navier-Stokes/Euler is still UNKNOWN: pinned export
  regeneration was active at reconciliation. No incorrect decisive result was
  observed in the completed cases; no result is imputed to the remaining case.
- Large jobs rebuilt identical source under the recorded Rust/compiler flags;
  their distinct executable hashes are retained. They are source qualification,
  not executions of the frozen native-timing binary.

Execution authorities: [native and portable run](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45711005244),
[large matrix](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45711718821),
[Cedar recipe recovery](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45712074107).
The first Cedar job failed before semantic execution because the multiline
recipe was split incorrectly. Recovery passed the exact original bytes; the
failed apparatus predecessor is not counted as a kernel reject.

## Completed diagnostic and rejected direction

The [old-core declaration census](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45710770234)
completed twice on the same full Mathlib. All 739,167 unique declaration indices
were checked in each archive. Top 100 declarations account for 8.9614% / 8.6403%
of recorded checking time, with 92/100 overlap. The prefix's 35.4% concentration
does not transport to the full input. This suggests diffuse checking costs on
the old core; it is not a profile of the reconciled core and not an instruction
lower bound. Raw full rows remain in the hash-pinned archive; summaries are
retained here.

The independently implemented old-core mutual-block receipt prototype passed
48 library tests and 44 process control observations. The source patch and
frozen fixture are retained. Its performance target is **SUPERSEDED**: the newer
core already reconstructs each complete mutual block once and persists its
derived terms. No performance, full portable or full Mathlib result is claimed
for the prototype. Reusable controls cover concurrent member checking and
receipt invalidation after a source mutation.

The source-derived controls were also run before preprocessing in the newer
core. No invalid input was accepted. The intentionally malformed control using
an undeclared universe Param produces raw exit 3 and an internal parser panic;
it remains an internal failure/UNKNOWN, not semantic REJECT. The added control
with duplicate *declared* universe parameters is rejected with raw exit 1. The
member-order case is differential only and has no independent semantic oracle.

## Remaining decisive evidence

[Complete calibrated instruction diagnostic](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45712976230)
is RUNNING at this checkpoint. It counts application basic-block instructions
including libraries after exact known-loop calibration. Its own documented REP
and asynchronous-interruption limits remain; even completion is not an official
Arena score. The PMU probe found no supported instructions event after testing
the disposable runner's access policy; this is unavailable measurement, not a
zero count or performance result. The older whole-input Valgrind comparisons
hit their declared budgets and remain UNKNOWN, not still running.

Next: resolve the one pending large input and complete instruction diagnostic,
then decide whether the reconciled candidate warrants release qualification or
needs another measured structural improvement. The published Flash release and
official rank are unchanged by this evidence-only commit.

`verify_archives.py` rechecks archive SHA-256/CRC, executable identities, native
rows, all portable outcomes, complete large-input identities and the full census
indices/sums against `archive-authorities.json`. It does not rerun the checker or
independently reconstruct all multi-gigabyte inputs. See
`independent-verification.json` for the executed assertions and remaining limits.
