# MathGraph Flash — upstream reconciliation experiment

This research branch uses Jeremy Chen's [sokonanoda](https://github.com/intgrah/sokonanoda)
at `9a021b66f804a1d1df68a981337c67413ef72f6b` as its checker core. Sokonanoda is
derived from [nanoda](https://github.com/ammkrn/nanoda_lib) and inspired by
[smalltt](https://github.com/AndrasKovacs/smalltt). The upstream Apache-2.0 license
and source copyright notices are retained. This is an attributed upstream
integration, not an independently implemented checker. Independent Nucleus is
a separate project.

The MathGraph changes preserve comparison with untrusted inductive, constructor
and recursor records when the upstream core reconstructs them. Changed rule
bodies must have checked types before value comparison. The branch also rejects
loose declaration values before preprocessing and carries the closed/open
natural-shift repairs. Self-referential unsafe or partial definitions are
rejected as kernel evidence; other unsupported unsafe inputs remain declined.
Errors and declines are not rewritten into acceptance.

The released Flash revision remains `819d59c34db3fd8f7b790a83f5728f255f75f33e`.
This candidate is not a release or a claim to first place. It used 23.66% fewer
software guest instructions on a fixed 25,131-declaration Mathlib prefix in two
alternating rounds. Complete Mathlib and all 240 current Arena statuses remain
separate gates. The initial portable run had 228 correct decisions and two
killed processes; the shift case has since been recovered. See the
[exact evidence and protocol](experiments/flash-upstream-repair-20261126/decision.json).

Build with Rust 1.99.1:

```sh
cargo test --locked
cargo build --release --locked
target/release/sokonanoda --stdin --threads 2 --nat-extension --string-extension --axiom-allow-all < export.ndjson
```

Native evidence includes 39 library tests and eight explicit retained export
controls. The optional Arena integration test does not qualify a corpus when
its input environment is absent. Three existing documentation examples are ignored.
