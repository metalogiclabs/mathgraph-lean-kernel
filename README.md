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
This candidate is proposed in [draft PR128](https://github.com/metalogiclabs/mathgraph-lean-kernel/pull/128).
It is not a release or a claim to first place. The exact complete Mathlib export
is accepted by both candidate and baseline in two alternating rounds:

| Median measurement | Released Flash | Candidate |
| --- | ---: | ---: |
| Total CPU | 245.195s | 164.685s |
| Wall time | 131.475s | 91.685s |
| Peak RSS | 6,486,390KiB | 4,838,646KiB |

That is 32.8% less CPU and 25.4% less peak RSS with two workers on that runner.
CPU seconds are not Arena retired instructions. All four processes checked
739,167 declarations from the unchanged 6,326,141,213-byte official input.

A separate one-worker full-input diagnostic completed both executions and
counted 964,868,458,684 baseline versus 545,995,448,357 candidate dynamic
basic-block application instructions: **43.41% fewer**. Its three analytical
loop controls pass. This is a software measurement, with different REP-string
accounting from Cachegrind, and is not official hardware scoring.

Current prescribed compatibility is **240/240**: all 230 portable cases and
all ten complete large inputs pass, including Navier–Stokes–Euler.
The [final joined qualification](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45717594082)
verifies the exact source, input identities and raw verdicts. Its downloaded
archive SHA256 and CRC, all 663 retained text-entry digests, and every input/verdict
join were independently checked. The 30 policy cases are outside this count. The earlier local killed processes are
preserved in lineage and superseded for these compatibility cases by successful
CI replays. See the [raw qualification capsule](experiments/flash-upstream-repair-20261126/qualification-capsule.json)
and [successful native workflow](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45711005244).

The fixed 25,131-declaration prefix used 23.66% fewer Cachegrind guest
instructions in two alternating rounds. Basic-block instruction estimates use
different REP-string accounting and are retained separately. Neither establishes
an official Arena rank. Source-only experiments with a
[single-binding key](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/cc271cc683771f1b0968dffbdf09134d8de8fa5f),
block-local validation sharing and 24-byte expression nodes remain unpromoted;
their patches and bounded outcomes are retained alongside the qualification.

Build with Rust 1.99.1:

```sh
cargo test --locked
cargo build --release --locked
target/release/sokonanoda --stdin --threads 2 --nat-extension --string-extension --axiom-allow-all < export.ndjson
```

Native evidence includes 39 library tests and eight explicit retained export
controls. The optional Arena integration test does not qualify a corpus when
its input environment is absent. Three existing documentation examples are ignored.
