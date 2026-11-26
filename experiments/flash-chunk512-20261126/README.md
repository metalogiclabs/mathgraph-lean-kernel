# Scheduling-batch candidate

Candidate source [4816054e](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/4816054e2331c3cd6b57cbcd51d3e265b48c68e7),
source tree `fa9f0de20650f28f63f1d01d7dab50397e167bcf`.
The sole checker change from qualified `bc704eeb` is `CHUNK_SIZE: 64 -> 512`.
It affects every parallel input equally; there is no benchmark-name dispatch.

Measured motivation: one worker reduces repeated work but slows elapsed
time on full Mathlib. Larger contiguous batches may retain more cache reuse
while using both workers. In two alternating prefix pairs with two workers,
the candidate uses **2.330% fewer software instructions**. All four processes
ACCEPT the exact 25,131 declarations. The candidate also passes 16 local
source controls, whose launcher uses one worker. Broad two-worker
qualification has subsequently passed 239 non-Mathlib prescribed cases;
their independently verified receipts are retained in `qualification-239/`.

Increasing the batch size preserves the cache's forward-order invariant:
atomic task claims increase within each worker, and each claimed range is
checked in increasing declaration order. Ranges remain disjoint and cover
the original file. No type-checking rule, metadata validation, environment
limit, inference cache key or proof comparison is changed.

The complete qualification freezes one generic executable and requires 39
library tests, eight retained raw-export cases, 230 exact portable outcomes
with two workers, 16 source controls with two workers, and all nine remaining
large-input ACCEPTs with their exact hashes/counts/timeouts. The optional
empty corpus test is not a corpus replay; three existing doctests remain
ignored. One complete generic Mathlib execution per arm follows exact loop
and explicit two-thread coverage controls. Matched native executables are
built and run on the same measurement host in alternating pairs.

The performance priority gate is at least 1% lower full-input software
instructions with all compatibility gates passed. Native CPU, wall time
and RSS are separate diagnostics and must be reported with their tradeoffs.
Generic and native measurements must not be conflated. Native compatibility
for the other nine large exports is outside the generic replay boundary.
No official hardware score, #1 rank or release promotion is assumed.

The already submitted Arena PR398 stays on qualified source bc704eeb and
two workers while this candidate is assessed. No duplicate Arena PR is made.

The slow software-counting comparison must not hold correctness evidence
hostage to instrumentation availability. `qualify_frozen_whole.py` separately
restores byte-identical generic candidate 878d871f from archive 15079511997,
verifies archive CRC/SHA, source identity and original complete-input SHA,
and runs the final Mathlib correctness case directly with two workers.
Its result remains pending until independently verified. It establishes no
instruction effect or rank and does not alter the active comparison.
