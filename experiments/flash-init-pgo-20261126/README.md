# Init-trained compiler experiment

CANDIDATE. Checker source remains `bc704eebed4e009bc66af1a849f18315c11f1926`,
source tree `06c257f0f2ff1f64711cfa54620b650e6dd59b7e`.

Both current Arena leaders use profile-guided compilation trained on Init:
[nano-lean's descriptor](https://github.com/leanprover/lean-kernel-arena/blob/04c2e955ce32a43e0f3e3c0a473c25215dd2afea/checkers/nano-lean.yaml)
and [Gruszka's descriptor](https://github.com/leanprover/lean-kernel-arena/blob/04c2e955ce32a43e0f3e3c0a473c25215dd2afea/checkers/gruszka.yaml).
This experiment independently implements conventional Rust/LLVM PGO for the
already credited sokonanoda-derived Flash core. It uses nano-lean's published
Init **data asset**, pinned by its published compressed SHA-256. No competitor
kernel implementation is copied.

The control and candidate share source, compiler, native CPU target and CLI.
Explicit Cargo targets keep host build scripts and procedural macros out of
the checker training profiles. Only two Init checking executions, one with
one worker and one with two workers, enter the merged profile. Atomic profile
counter updates preserve multithreaded training counts. Mathlib is never
executed for training. Init is part of Mathlib's mathematical foundation;
this is not an out-of-distribution claim.

The experiment requires 39 library tests, the eight retained source-export
regressions, 230 exact portable prescribed outcomes, 16 additional source
controls, and complete 739,167-declaration Mathlib ACCEPTs from both binaries.
The optional empty-corpus test is not a corpus replay; three existing
documentation examples remain ignored. PGO compatibility for the other nine
large exports is not established by these gates.

Two alternating pairs measure native CPU, wall time and RSS. A separate
one-worker, one-execution-per-arm software instruction diagnostic uses the
existing pinned DynamoRIO client and three analytical loop controls. These
results cannot establish an Arena hardware instruction score or rank.

This workflow does not update either release reference or the pending
[official Arena submission](https://github.com/leanprover/lean-kernel-arena/pull/398).
Promote only after observing and independently verifying the actual results.
The earlier prefix-trained PGO experiment remains a separate training-only
result; its 1.97% prefix gain is not reused as evidence for this experiment.


## Completed outcome

[Run45729265712](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45729265712)
completed successfully. Artifact15076991448 (57,038,303 bytes) independently
matches SHA-256 `a58fc7871d0513b413643fff15fbb83fda1f84b056c133f31688f2f377cb2b56`
and ZIP CRC. All572 archive entry digests and both actual executable hashes
were recomputed. See `verified-comparison/` and the shared
`../flash-continued-cost-trials-20261126/verify_diagnostic_archive.py`.

The ordinary native binary counts515,628,583,473 software instructions;
Init-PGO counts508,341,361,994: **1.413% fewer**, one complete execution per
arm and three exact loop controls. Both ACCEPT739,167 declarations.
Native median CPU is155.760s versus154.630s (0.725% lower), but the two
paired directions disagree (-2.384%, +1.041%). That small CPU difference
is not strong evidence of a practical CPU gain. All39 library tests,
eight retained raw exports,230 portable prescribed outcomes and16 source
controls pass. The other nine large exports were not replayed with this
PGO executable. No native PMU result or Arena rank follows.

The merged compiler profile is retained as `verified-comparison/training.profdata.gz`
(62,670 bytes), with its original393,392-byte profile hash and compression
identity, so it survives expiry of the Actions artifact. The exact training
input is348,430,202 bytes, SHA-256 `e819664a1c7d7df8dc303077a9f85be2a1d24bc60d57636b64570edff83e5724`;
both training executions ACCEPT59,626 declarations. Only their two actual
checker profiles enter the merge.

**Decision: retain the measured build candidate and reusable protocol; do
not promote it into PR398 for this small gain and uncompleted large-input
boundary.** Its gains cannot be multiplied by worker or inline results.
