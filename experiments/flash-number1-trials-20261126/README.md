# Independent Flash performance trials — 26 November 2026

Objective: reduce the current qualified checker’s instruction cost while preserving its prescribed verdicts. All implementation changes here were independently authored against Flash. Competitor implementations were inspected for design comparison; no competitor source was copied into these patches.

The latest official raw results place the qualified Flash release fifth with zero incorrect prescribed verdicts, at 155.276 virtual seconds on Mathlib. The still-stale public site shows the older last-place revision. Matching the leader’s 65.814 seconds requires 57.615% fewer instructions; the precise source and ranking reconstruction are recorded in `arena-gap.json`.

The official release remains `819d59c34db3fd8f7b790a83f5728f255f75f33e`. These are research trials, with no release promotion or Arena submission.

| Trial | Five-case guest instruction ratio | Decision |
| --- | ---: | --- |
| Exact original-environment cache aliases | 1.123513 | Rejected for performance promotion |
| Separate bounded early cache | 1.016989 | Rejected for performance promotion |
| Syntactically unused lambda argument | 1.002592 | Rejected for performance promotion |
| Variable bit in expression handle | 0.998950 | Below the predeclared 1% material gate |
| Compound argument call-by-need | 1.063353 | Rejected for performance promotion |
| Retain full evaluation environment | 1.047383 | Rejected for performance promotion |
| Table hashing dependency only | 1.000452 | Below material gate; no demonstrated improvement |

Ratios below 1 are cheaper. They are geometric means across `init-prelude`, `perf/grind-ring-5`, `perf/magma-list-deep-n21`, `perf/magma-list-pair-n7` and `perf/fueled-chain`. Every compared input’s bytes and SHA-256 match official run 45581042122. The measurements use generic x86-64, one worker, Rust 1.99.1 and Valgrind 3.22 software guest instructions. They are not official Arena scores, full-Mathlib measurements, or statistical confidence intervals.

Earlier cache trials and the diagnostic census are preserved at [951b5af3](https://github.com/metalogiclabs/mathgraph-lean-kernel/tree/951b5af3b80e5b1250048073029a5b7050f8459c/experiments/flash-early-eval-cache-20261126).

The five subdirectories preserve source patches, input and binary identities, raw process statuses, measurements and decisions. Their patches independently apply to [fixture-only base ca69e6ab](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/ca69e6ab8a3c7b795716128372fdaf67c697b68e); they must not be stacked. The source on this branch is the full-environment experiment, independently based on the same fixture-only base.

The restored fixtures fix two missing tracked files in existing regression tests, without changing the production baseline. Their provenance and byte-level mutations are recorded in the fixture directories.

## Qualification boundaries

- Syntactic unused argument: 51 library unit tests; 227 correct statuses in 228 attempted portable cases, with one SIGKILL of unknown cause. Two earlier common SIGKILL cases were not retried.
- Tagged variable: 48 library unit tests; 228/228 attempted portable statuses correct; those same two cases not retried.
- Call-by-need: 54 library unit tests and all five positive comparison cases accepted. Broad portable and full-Mathlib qualification were not attempted after the failed cost gate.
- Full environment: 47 library unit tests and all five comparison cases accepted. Broad portable and full-Mathlib qualification were not attempted after the failed cost gate.
- A passing unconfigured integration test is not corpus qualification. Four existing doctests are ignored.
- No trial above is a fully qualified replacement release. Failures, missing cases and unknowns remain in the receipts.

## Replay

Apply exactly one preserved patch to the fixture-only base, run `cargo test --locked`, and compile baseline and candidate with identical flags:

```sh
RUSTFLAGS='-C target-cpu=x86-64 -C target-feature=-avx,-avx2,-avx512f,-fma' cargo build --release --locked
```

With the hash-matched official results and extracted portable fixtures, run the shared `compare.py samples` harness with `--results`, `--fixtures`, `--baseline`, `--candidate`, `--out`, and `--valgrind` paths. The harness preserves exit codes, never supplies case names to the checker, and fails on a wrong or unavailable status. The portable mode attempts all 230 prescribed small inputs; known local SIGKILLs are not silently recategorized as correct rejections.

## Full Mathlib discriminator

The small-case cost gate rejected both architectural variants, but does not establish their full-Mathlib performance. A separate diagnostic reconstructs baseline, call-by-need and full-environment arms independently, verifies their exact source trees, runs their library tests, regenerates the current official 6,326,141,213-byte Mathlib input and verifies its SHA-256. It then runs each arm twice with alternating order, one worker, Rust 1.99.1 and the same native compilation flags.

`whole_mathlib.py` requires strict exit 0 and the checker’s complete-check success message. It records CPU time, wall time and peak RSS. Hardware instructions are recorded only when the explicit PMU probe succeeds. CPU time is never called an Arena virtual time. This is a workload discriminator, not full 240-case qualification. The current [full-Mathlib run 45686409325](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45686409325), head dd3982d500513a76b150d3f67ff7eef60a32d2bb, has passed independent source reconstruction and the three library suites; export and performance results remain pending at this checkpoint. Its result is UNKNOWN until the actual receipts are checked.

All five patches in this directory were independently reapplied to the fixture-only base through a fresh Git index. Every reconstructed source tree matches the tree executed in its trial; see `patch-reconstruction.json`. This verifies replayable source identity, not corpus qualification.
