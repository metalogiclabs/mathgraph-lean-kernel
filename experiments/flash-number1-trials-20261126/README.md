# Independent Flash performance trials — 26 November 2026

The current candidate removes the additional open-expression evaluation memo table. Closed evaluation caching, closure support projection, value interning, inference and all correctness guards remain in place. Its exact measured source tree is `6b5f867d4b371dcf0d7cdfc38d14e4507ba621e1`.

The candidate passed 47 local library tests, all 228 locally attempted portable inputs, and a separate native runner qualification of all 230 prescribed portable inputs with two workers, official per-case timeouts and no exclusions. The latter artifact was independently hash-verified; see `remote-portable-230/verification.json`. Its first five-case instruction comparison improved geometrically by 1.23%; a separate two-round alternating-order comparison improved by 1.25%, with all 20 process statuses correct. The tradeoff is substantial: about 25% fewer instructions on magma-pair n7, but about 30% more on fueled-chain. This is a candidate for further measurement, not a general speedup or a qualified replacement release.

The corrective workflow rechecks the original 230-case artifact against the unchanged production source before comparing baseline and candidate on exact full Mathlib. Each arm gets a fresh Cargo target directory. Its expected unit-test count and a distinct release-executable SHA-256 are required before measurement. Both native arms use the official release’s two-worker setting. Full Mathlib input is pinned by size and SHA-256 and cached after successful qualification to avoid regenerating the same 6.3 GB for every experiment. Hardware counters are used only when the explicit PMU probe succeeds; CPU seconds are never called Arena virtual seconds. The [corrected full-Mathlib run 45692268504](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45692268504), head ba0a6f99a1bb2be3535ebe61bcf4a9a111dff417, is in progress. Its performance result is UNKNOWN.

## Warranted baseline and objective

The official release remains `819d59c34db3fd8f7b790a83f5728f255f75f33e`. The latest official raw artifact has 240/240 prescribed statuses correct and computes to fifth place, at 155.276 virtual seconds on Mathlib. The still-stale public site shows the older last-place revision. Matching the leader’s 65.814 seconds requires 57.615% fewer instructions. `arena-gap.json` records the source, scoring reconstruction and distinction between raw-artifact rank and the published site.

All implementation changes here were independently authored against Flash. Competitor implementations were inspected for design comparison; no competitor implementation was copied. The table-hasher trial uses the separately licensed rustc-hash dependency normally, while preserving the original structural digest algorithm. MathGraph remains an explicitly credited sokonanoda derivative; these trials do not claim an independent checker rewrite.

## Measured trials

| Trial | Five-case guest instruction ratio | Decision |
| --- | ---: | --- |
| Exact original-environment cache aliases | 1.123513 | Rejected for performance promotion |
| Separate bounded early cache | 1.016989 | Rejected for performance promotion |
| Syntactically unused lambda argument | 1.002592 | Rejected for performance promotion |
| Variable bit in expression handle | 0.998950 | Below the predeclared 1% material gate |
| Compound argument call-by-need | 1.063353 | Rejected; two later portable processes killed |
| Retain full evaluation environment | 1.047383 | Rejected by small-case cost gate |
| Table hashing dependency only | 1.000452 | Below material gate; no demonstrated improvement |
| Remove open-expression memoization | 0.987525 | Repeated cost gate and all-230 portable passed; full Mathlib performance pending |

Ratios below 1 are cheaper. Each ratio is the geometric mean across `init-prelude`, `perf/grind-ring-5`, `perf/magma-list-deep-n21`, `perf/magma-list-pair-n7` and `perf/fueled-chain`. Every input matches official run 45581042122 by bytes and SHA-256. Local measurements use generic x86-64, one worker, Rust 1.99.1 and Valgrind 3.22 software guest instructions. They are not official Arena scores, full-Mathlib measurements, or statistical confidence intervals. The final row uses the independent two-round repeat; other rows use one observation per arm and case.

Earlier cache trials and the diagnostic census are preserved at [951b5af3](https://github.com/metalogiclabs/mathgraph-lean-kernel/tree/951b5af3b80e5b1250048073029a5b7050f8459c/experiments/flash-early-eval-cache-20261126). That census motivated the final ablation: the cost of constructing canonical environment keys may exceed the benefit of some open-expression memoization. This mechanism remains a workload-dependent hypothesis.

Each implementation patch independently applies to [fixture-only base ca69e6ab](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/ca69e6ab8a3c7b795716128372fdaf67c697b68e). Do not stack the patches. The source on this branch now equals the final ablation’s measured source tree. `patch-reconstruction.json` verifies exact source reconstruction, not corpus qualification.

## Qualification boundaries and negative results

- Syntactic unused argument: 51 library tests; 227/228 attempted portable statuses correct. GF3 was killed with cause unknown. Two earlier common killed cases were not retried.
- Tagged variable: 48 library tests; 228/228 attempted statuses correct, same two exclusions.
- Call-by-need: 54 library tests; later portable run 226/228. Both `ite-taken-branch` and its invalid companion were killed. A repeated native resource control accepted/rejected both cases correctly on baseline and full-environment arms, while the delayed arm was killed again. Peak RSS was higher for the delayed arm; cgroup kill counters were unavailable, so the precise kill cause remains UNKNOWN. See `architecture-portable/`.
- Full environment: 47 library tests; 228/228 attempted portable statuses correct, same two exclusions.
- Table hasher: 46 library tests and five accepted comparison cases; no broad corpus qualification after the failed cost gate.
- No open memo: 47 local library tests; 228/228 local portable statuses correct with two exclusions, then 230/230 native runner portable statuses correct with no exclusions; 20/20 accepted repeat measurement processes.
- An unconfigured integration test is not corpus qualification. Four existing doctests are ignored. No local trial has full 240-case qualification.

## Invalidated full comparison and correction

[Run 45686409325](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45686409325), head dd3982d500513a76b150d3f67ff7eef60a32d2bb, is an invalid variant comparison. Source trees differed correctly, but shared Cargo target directories reused the same baseline executable and unit executable in all arms. All three binary SHA-256 values are identical and every arm ran 46 baseline library tests. Its apparent CPU differences do not measure code changes. The original artifact was hash-verified and its observations are preserved under `invalidated-shared-target/`. Do not promote any variant performance or remote unit-suite claim from that run.

The same issue affects the Mathlib stage of [run 45691028748](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45691028748). Its separate portable job is valid and supplies the 230/230 result; its shared-target Mathlib stage was superseded and canceled by the corrective workflow. The corrective workflow stops that stage, reverifies the valid artifact for identical source, builds every comparison arm in a fresh target directory, checks baseline 46 versus candidate 47 library tests, and rejects identical release executables. The measurement harness independently rejects identical binary hashes as well.

All local trials used separate target directories. Their recorded baseline and candidate binary hashes are distinct. The shared-target error does not invalidate those bounded local measurements.


The fixture-only base restores two missing files required by existing regression tests without changing the production baseline. Provenance and byte-level mutations are recorded in those fixture directories.

## Replay

Apply exactly one patch to the fixture-only base, run `cargo test --locked`, and compile baseline and candidate with identical flags:

```sh
RUSTFLAGS='-C target-cpu=x86-64 -C target-feature=-avx,-avx2,-avx512f,-fma' cargo build --release --locked
```

Run `compare.py samples` with `--results`, `--fixtures`, `--baseline`, `--candidate`, `--out` and `--valgrind`. `--rounds 2` reverses order in the second round. The final ablation used an explicit 60-second per-process diagnostic cap; earlier comparisons retained the harness defaults. `portable_variants.py` records exclusions as unknown, preserves raw process statuses, and can use the actual official per-case timeouts. Case names are never sent to checker processes.
