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
