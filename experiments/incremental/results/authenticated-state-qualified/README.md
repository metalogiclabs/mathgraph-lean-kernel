# Authenticated warm-state qualification

**WARRANTED on the pinned Lean/Std workloads:** changed-input verification using authenticated construction state beats direct fresh Rust checking, agrees with independent full checking, and preserves the existing conservative reuse decisions. The exact-source CI and a separately built local replay both pass. This extends the earlier qualified revision-chain result; it does not replace its evidence or claim universal Lean soundness.

- Runtime/source: [`cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5`](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5).
- Branch: [`research/incremental-authenticated-state-20261022`](https://github.com/metalogiclabs/mathgraph-lean-kernel/tree/research/incremental-authenticated-state-20261022).
- Successful exact-source CI: [39709067518](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/39709067518).
- Canonical Research OS: [incremental-checking checkpoint](https://app.notion.com/p/3fb3e523d7ab81c68c89c1442eb0bb05).
- Prior source/checkpoint: `b1931f8479a2bcd78af85ba79e60958963f89d96`; prior qualified runtime `d1b22447d23a928ae536cbe838a47fc9682a4b39`, evidence `d5aa24cc52f6a38c79d097be58226547181cc97b`.

## What changed and why

The prior work already supplied the genuine Lean source owner, authenticated deltas, retained typed dependency/SCC index, sparse receipts, conservative applicability predicate, real selected Rust kernel, independent full oracles and MathGraph evidence integration. This implementation reuses them. Rust checker/index code, `engine.py` and the Lean source producer are unchanged from the prior checkpoint.

The remaining repeated work was composing a complete successor export, hashing it, and reading it back during promotion. `StateChainSession` retains immutable verified-genesis slices and exact authenticated delta constructions instead. New receipt domains bind accepted parent state/evidence, source root, policy, revision and delta. Warm results expose a `state_id` and explicitly no complete-export SHA. Exact full materialization remains an explicit operation, used outside primary timers for independent comparison.

Across forty updates, the prior adapter materializes, hashes and rereads 636,892,477 bytes on the original workload or 2,564,646,194 bytes on the expanded one. The state path records zero for these full-export operations while consuming 4,764/4,795 delta bytes. Both paths already avoid complete-export disk writes through sealed memfd, so this is not a disk-write saving. Median forty-update recipe/materialization time falls 1.030914→0.007945 seconds and 4.267744→0.008541 seconds respectively. Previous full-byte counts are derived from exact lengths and frozen implementation; state zeros are measured/source-tested counters.

## Measured economics

Five paired CI repetitions per workload, rotating the three arm orders. Each life includes constructor/start, real genesis admission, forty actual source-owned updates, receipt/head persistence and supported close. Direct performs forty-one fresh Rust checks on **identical actual exports**; preparing those inputs is excluded from its timer, favoring direct Rust.

| Obligations | Direct Rust life | Prior full-export adapter | State life | Less time vs direct | Speedup vs direct | Less time vs prior |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 3,436 | 11.911577 s | 7.893787 s | 6.645194 s | 44.2123% | 1.792510× | 15.8174% |
| 11,653 | 55.110394 s | 32.149496 s | 26.484562 s | 51.9427% | 2.080850× | 17.6206% |

| Warm edit | Direct Rust | Prior adapter | State | Speedup vs direct | Less time vs direct | Less time vs prior |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 3,436 / early | 291.482 ms | 117.295 ms | 84.613 ms | 3.444874× | 70.9714% | 27.8626% |
| 3,436 / unrelated | 291.589 ms | 78.225 ms | 49.185 ms | 5.928413× | 83.1321% | 37.1237% |
| 11,653 / early | 1,353.400 ms | 428.339 ms | 322.108 ms | 4.201692× | 76.2001% | 24.8006% |
| 11,653 / unrelated | 1,347.006 ms | 404.070 ms | 295.280 ms | 4.561787× | 78.0788% | 26.9235% |

Warm numbers are medians of five per-pair means of ten same-kind edits, not pooled latency medians. All eight primary warm comparisons independently win 5/5 pairs and have a 95% paired-bootstrap ratio upper bound below one. All lifecycle wall/CPU and restoration comparisons also independently pass. The separate arithmetic reader exactly reproduced all 28 published series, raw arrays and 10,000-resample bootstrap intervals.

State lifecycle CPU is 6.644491/26.515758 seconds versus direct 11.915380/55.110503 seconds: 44.2360%/51.8862% less. **Cold initialization does not win:** 3.908941/15.048562 seconds for state versus 0.288635/1.351731 seconds for one fresh Rust genesis check. Separate expected-head forty-revision cold recovery is 6.058689/25.518376 seconds, one observation per workload, and replays prior acceptance history rather than freshly checking genesis. Forty-update measurements establish no general break-even point.

Logical persisted payload slightly grows: 20,605,642/103,460,296 bytes versus prior 20,575,155/103,429,809 bytes. Per-process RSS/VmHWM samples and phase CPU/wall data are preserved; they establish no aggregate peak or memory saving. See [the independent performance review](performance/REVIEW.md), complete JSON and CSV observations.

## Independent correctness boundary

The source-frozen CI passes the original 197 gates, native 335, independent 719, separately compiled original-source 251, and protected retained-parser 246/229 aggregations. Counts overlap and must not be summed as independent theorems. Historical original-source executables are separately built at `9ac04033b51703fb135ec3c28621d44b183944fe`; they are not claimed byte-identical to old CI binaries. The compact package carries the protected aggregator, not its complete detailed matrices; the full CI artifact contains the raw files.

New real representation tests reproduce four changed/cold-replayed revisions per workload and unchanged zero-selected acceptance. The new adversarial suites have 50 distinct required controls per workload, all passing. They cover forged/foreign authority, wrong parents/domains/environment/version, source outside the reported region, false name hints, axiom and invalid-source changes, dependency-edge fallback/refresh/restoration, unused DAG changes, corrupt storage and missing heads, receipt corruption and failed persistence. The native parser still consumes every changed row even when zero obligations are selected.

Each workload records seven explicit `UNKNOWN` update results and two `REJECTED` results. UNKNOWN is refusal to warrant, not proof of invalidity; exception refusals without a status remain distinct. The rejected proof and malformed-unused-DAG inputs have no accepted state ID/evidence and are independently rejected by Rust, C++ and paranoid C++. Key-resigned parser fixtures possess issuer authority and are not described as real producer outputs or attacker-forged HMACs. Persistence failure poisons speculative processes and preserves the accepted head; a previously kernel-accepted orphan receipt can remain on disk without promotion.

After downloading and verifying all 8,346 compact files, a **separate local build from exact clean CEC source** executed the committed standalone reader without importing the incremental engine or issuer and without `--allow-smoke`. It passed:

- 800 primary transitions and 7,242,720 declaration-witness comparisons, including all resulting fingerprints, full-index partitions and reuse/check decisions. Witnesses repeat across arms/revisions; these are not unique declarations.
- 108 fresh kernel processes: 80 positive changed exports checked by Rust, 16 representative positive C++/paranoid checks, and twelve negative runs across the three kernels.
- 100 controls and 190 content-addressed archive objects. Complete exact input bytes were independently reconstructed and compared with the exported full witnesses.

Fresh replay summary SHA256: `7a83a91d5d498741b9d81db4226a0c5cf6c048d4ce658a2056b98ad5e9ab5175`. No soundness mismatch, timeout, unsupported-input acceptance or checker disagreement occurred in this qualified set. The public readers do **not** reauthenticate historical HMACs because the secret is deliberately absent; actual-key authority tests ran inside CI. Public replay independently establishes exact-input/fingerprint/decision/kernel agreement. See [correctness inventory](correctness/review.txt), [fresh replay](independent/summary.json), and [replay instructions](REPLAY.md).

## Trust and remaining residual

No issuer, secret-key principal, kernel implementation or applicability rule is replaced. Private source-owned immutable state, pinned imports/toolchain/policy, and caller-supplied expected-head latestness remain assumptions. A valid historical prefix is not latestness authority. Construction serialization and its receipt bridge are new trusted executable code, qualified here by exact-byte reconstruction and independent oracles. A construction-state ID is neither a full-export SHA nor a semantic-equivalence proof. The earlier bounded Lean model does not formally verify this whole executable bridge.

Warm updates avoid whole-export materialization/hash/readback, but total verification is still **not asymptotically change-proportional**. Initial admission, explicit export and cold recovery remain substantial; retained index copying, applicability, decision and receipt traversal still visit whole-index structures. Expanded warm time now spends 47.3687% in persistence and 22.2097% in the consumer gap, versus 20.5556% in genuine checking. Promotion is nested in persistence. These aggregate phases do not identify individual Python operations without further profiling.

A separate local exploratory probe refused the proposed equal-cone scaling experiment: the same genuine leaf edit checks 1/3,436 obligations but 260/11,653. Only the leaf fingerprint changes and the retained index recomputes one SCC; 259 unchanged later obligations (70 inductive types, 119 constructors, 70 recursors) receive `complex_outside_verified_prefix`. Fresh full-index/Rust comparison confirms the result. No five-pair fixed-cone benchmark was fabricated. This probe is preserved under `exploratory/`, explicitly outside CI qualification.

**Smallest economic residual:** isolate and qualify sparse applicability/receipt validation within the remaining persistence/consumer phases while preserving exactly the current decisions. The stronger question of truly cone-proportional total verification also requires an independently justified warrant for unchanged complex declarations outside the verified prefix. It remains UNKNOWN; no unrestricted Lean, Mathlib-scale, universal soundness or whole-pipeline formal-verification claim is promoted.

## Evidence and lineage

[Artifact index](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/39709067518/artifacts/12405617778), [compact 00](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/39709067518/artifacts/12406026073), [compact 01](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/39709067518/artifacts/12406205607). Exact provider bytes are permanently preserved under `provider/`; `transport/` reuses the prior unchanged ZIP-part reconstructor and verifies inner manifests and every leaf. Whole compact XZ SHA256: `e02e8de94fbc38f5d9c249eadc93bd1c59aaa1f713a05e04da2e3ed3e1a01972`.

CI run/job/artifact metadata, source/build pins, arithmetic/transport/correctness proofs, complete fresh replay outputs and tests are preserved alongside the inputs. The connector job-log segment covers 04:12:28–06:12:53 UTC; it is not a claim of complete job-log coverage. The six full provider parts are remote-only here, with exact provider IDs/digests recorded. Their raw bytes were not independently downloaded or replayed locally.

Prior stronger qualification remains intact. Development failures, the deliberately unfavorable four-update smoke, parser framing regression test, independent-reader falsifiers and the local missing-time-launcher failure are retained with their limited scopes. The missing `/usr/bin/time` launcher failed before executing the qualified reader; Python standard-library resource measurement repaired only the outside-repository audit wrapper. The actual successful source/reader never changed. This evidence-only update does not modify runtime source, protected branches, or production deployments and makes no external submission.
