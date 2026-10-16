# Native identity qualification: adapter acceleration, direct Rust still faster

WARRANTED_BOUNDED: an optional native identity observer accelerates the complete existing adapter while preserving the qualified reuse rule and decisions. The primary claim that changed-input verification beats direct fresh Rust checking is **not promoted**: both primary economic gates fail locally and in exact-source CI.

Implementation: [`1445e29`](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/1445e293238abedfb9f0cf727f6c5e17fd685184), continuing qualified source `9ac04033b51703fb135ec3c28621d44b183944fe`. Diagnostic/reporting follow-ups are `c424f8d` and `f6eaaff`; CI fail-closed repair is `c5ab126`; the engine and Rust implementation are unchanged. All inputs remain pinned Lean 4.35.0 / exporter 3.1.0 / Rust 1.95.0.

## Exact-source CI qualification and measured outcome

[Run 38885278602](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38885278602) qualifies source [`c5ab12699338aa57b7e9d48b15d4a7409e453c7b`](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/c5ab12699338aa57b7e9d48b15d4a7409e453c7b). Actual decoded logs and the independently downloaded compact archive confirm 197/335/719/251 nonempty passing correctness gates, 21 fresh full-oracle decisions and five passing unchanged MathGraph integration cases. Explicit Bash pipefail and its failing-pipeline negative control ran. **The economic outcome is NO_SPEEDUP**; green CI qualifies bounded correctness, not a direct-Rust performance win.

The CI host is a separate five-pair observation, not pooled with the local results below. Complete command medians, seconds:

| Case | Frozen Python full | Native full | Native incremental | Current direct Rust full |
|---|---:|---:|---:|---:|
| baseline | 4.320825 | 0.636173 | 0.181911 | 0.222530 |
| early-definition | 4.339893 | 0.635886 | 0.474243 | 0.232772 |
| unrelated-definition | 4.331822 | 0.626173 | 0.454681 | 0.232642 |
| theorem-leaf | 4.348201 | 0.615752 | 0.454159 | 0.232608 |
| invalid-proof | 4.199176 | 0.504923 | 0.312999 | 0.232625 |
| axiom-type | 4.036073 | 0.292858 | 0.333285 | 0.030727 |

Early edit saves 89.07% versus frozen Python full and 25.42% versus native full, but is 103.74% slower than direct Rust (2.03737 ratio, 0/5 paired native wins, 95% bootstrap [1.83393, 2.13276]). Unrelated saves 89.50% and 27.39%, but is 95.44% slower than direct Rust (1.95442 ratio, 0/5 wins, interval [1.90842, 1.99976]). CPU medians also lose: native 0.369741/0.351083 s versus raw 0.225714/0.226668 s. The frozen 9ac direct-Rust medians 0.232633/0.232826 s support the same decision.

CI early/unrelated complete identity wall costs0.176641/0.181664s (native subprocess0.149353/0.153954s); cache validation0.044528/0.044474s; actual selected checking0.042100/0.018963s; receipt/export persistence0.130992/0.130079s (CPU0.033941/0.034354s). Persistence has about0.096–0.097s wall-minus-CPU time on this host. Its code performs immutable export/record writes and fsync; these measurements do not by themselves isolate the precise waiting cause. Startup/final output also remain in complete-process time. Instrumented memory timings are excluded from these medians. Avoiding all that persistence waiting alone would still leave both cases slower than direct Rust.

[Full artifact12039976400](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38885278602/artifacts/12039976400) retains 802,162,434 bytes with provider SHA256`1993750aa7cf5373b51c3315d4f3c3c15796fd5a55aa7af0d352b485dbf0ba79`. [Compact artifact12039714166](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38885278602/artifacts/12039714166) is 1,434,999 bytes; its SHA256`a9d73d4c1185d02da21ed53021ba58f651e28733d3e29125363dcea196daefa4` was verified against downloaded ZIP bytes. That exact [ZIP](ci-c5ab126-summaries.zip) is committed, preserving summaries/logs beyond artifact retention. The full ZIP exceeds the connector512MiB cap and workspace proxy permits no direct artifact-storage CONNECT; independent full-ZIP download is not claimed. [ci-qualification.json](ci-qualification.json) records exact metadata, every median/phase, paired economics, notices and source links.

The separate [archive review](ci-independent-archive-review.json) passes 26,753 content/source/protocol/arithmetic checks and all ten [reviewer negative probes](ci-archive-review-negative-controls.json) fail closed. It does not execute kernels or reauthenticate historical HMACs: the compact archive omits those caches and keys; qualified CI and repaired local replay performed the actual 21 oracle and 719 receipt checks. To recheck the committed compact archive from any repository checkout containing source c5ab126:

```sh
python3 experiments/incremental/results/native-qualified/review-ci-archive.py \
  --zip experiments/incremental/results/native-qualified/ci-c5ab126-summaries.zip \
  --artifact-metadata experiments/incremental/results/native-qualified/ci-compact-artifact-metadata.json \
  --source c5ab12699338aa57b7e9d48b15d4a7409e453c7b --repo . \
  --out /tmp/mathgraph-native-ci-archive-review.json
```

## Complete-process local measurements

Five paired repetitions; fresh command processes, warm OS file cache, randomized retained order. Seconds are medians. The workload exports actual Std.HashMap dependencies: 3,436 flattened obligations, 305,572 NDJSON rows, 15,922,029 bytes for the primary edits. No competing local qualification processes ran during the paired benchmark.

| Case | Frozen Python full adapter | Native full adapter | Native incremental | Current direct Rust full | Native incremental CPU |
|---|---:|---:|---:|---:|---:|
| baseline | 4.378585 | 0.639063 | 0.193072 | 0.325205 | 0.188143 |
| early-definition | 4.604797 | 0.670343 | 0.456439 | 0.304810 | 0.439218 |
| unrelated-definition | 4.475202 | 0.678897 | 0.435223 | 0.294227 | 0.418746 |
| theorem-leaf | 4.470090 | 0.678607 | 0.415557 | 0.314204 | 0.404286 |
| invalid-proof | 4.531492 | 0.598218 | 0.384950 | 0.304888 | 0.380384 |
| axiom-type | 4.254178 | 0.324907 | 0.395425 | 0.030862 | 0.389259 |

| Primary case | Reduction vs Python full | Reduction vs native full | Slower vs direct Rust | Paired native-incremental wins vs direct Rust |
|---|---:|---:|---:|---:|
| early-definition | 90.09% | 31.91% | 49.75% | 0/5 |
| unrelated-definition | 90.27% | 35.89% | 47.92% | 1/5 |

The early direct-Rust ratio is 1.49745 with paired-bootstrap 95% interval [1.10454,1.66525]; unrelated is 1.47921 with interval [0.79257,1.59202]. The prespecified gate requires a lower median, strict paired-win majority and upper bootstrap bound below 1 for both primary edits. Both fail. A win on unchanged bytes does not satisfy this gate.

## Remaining measured cost

Wall/CPU phases below are medians from the native incremental process. Identity includes current-export hashing, the native subprocess and index-protocol decoding; nested phases overlap and must not be summed.

| Phase | Early wall / CPU s | Unrelated wall / CPU s |
|---|---:|---:|
| Authenticate prior evidence | 0.051625 / 0.051624 | 0.049610 / 0.048664 |
| Copy changed bytes | 0.005205 / 0.005158 | 0.004273 / 0.004276 |
| Hash all changed bytes | 0.012599 / 0.012603 | 0.012546 / 0.012525 |
| Native parser plus typed identities | 0.172623 / 0.173769 | 0.182110 / 0.181506 |
| Complete identity path | 0.212802 / 0.213945 | 0.223009 / 0.222410 |
| Actual selected kernel | 0.053383 / 0.052200 | 0.019218 / 0.018653 |
| Export and signed receipt persistence | 0.054637 / 0.045487 | 0.054467 / 0.047600 |
| Engine total | 0.385577 / UNKNOWN | 0.362103 / UNKNOWN |

The engine total excludes Python startup and final result serialization/write; the complete-process table includes them. Native indexing still visits the full typed DAG. File hashing, parsing, export construction and complete receipt/result production remain proportional to the full input or obligation set. No authenticated producer delta or change-proportional total runtime is established. The isolated receipt-byte-reuse microprobe saves only 12–16 ms against a pre-final 161–194 ms direct-check deficit and was not installed.

## Construction, memory and cache

Build/export are separately measured pinned input-construction commands. Adding these measured components gives lifecycle subtotals, not a new single-command end-to-end measurement.

| Primary case | Build + export s | Export alone s | + Python full s | + Native incremental s | + Direct Rust s |
|---|---:|---:|---:|---:|---:|
| early-definition | 1.759386 | 1.016251 | 6.364183 | 2.215824 | 2.064196 |
| unrelated-definition | 1.978649 | 1.114645 | 6.453851 | 2.413872 | 2.272876 |

The original native qualification cache occupies 155,644,844 bytes: snapshots95,532,305, evidence60,112,539, 14 records. This is the whole qualification cache, not the working-set size or a minimum incremental cache.

Raw benchmark wait4 highwaters include inherited launcher memory and support no memory-saving claim. The separate [phase-memory diagnostic](../native-profile/phase-memory.md) validates expected decisions and reports post-exec native-child VmHWM around 97,240–97,272KiB, early selected 86,276KiB and sampled simultaneous RSS sums 130,004KiB early / 122,328KiB unrelated. These are distinct observations: sampling can miss peaks, cumulative maxima need not coincide, and RSS sums count shared pages twice. Unsampled short/GIL-bound phase peaks remain UNKNOWN. Instrumented memory-profile timings are excluded from economics.

## Correctness and independent boundary

- All 197 original gate names/order are preserved and pass, including HMAC authority, exact-export integrity, restart, cache/key/toolchain corruption and drift, restoration, no-evidence-on-failure and real changed-byte parsing when zero obligations are scheduled.
- All 335 differential gates pass over 10 pinned exports and 72 adversarial inputs. 45 supported native indexes equal complete Python canonical structures; 17 require explicit Python fallback; 20 are refused by both. Successful differential disagreement, malformed protocol, signal/crash or timeout cannot issue a receipt.
- Independent persisted-evidence replay passes 719 checks over 72 invocations and 35 record paths. 21 fresh full Rust/C++/paranoid processes independently accept the selected positives and reject selected negatives. The original mandatory 20 C++ normal/paranoid runs cover all 10 exports.
- Invalid proofs and changed standard-axiom types reject without new evidence. Malformed missing-reference input remains UNKNOWN; malformed unused typed input rejects after the actual Rust parser despite zero selected obligations. Acceptance is never inferred from a matching index.
- Early edit genuinely checks 413 / reuses 3,023 obligations (87.98% fewer checks). Unrelated/leaf checks 1 / reuses 3,435. Unchanged checks 0 / reuses 3,436. The actual selected kernel reports checked and total counts; authenticated adapter partitions establish the reused counts and independent replay validates those partitions.
- All 251 benchmark correctness gates and 1,704 independent arithmetic/protocol/source review checks pass. The unchanged pinned MathGraph consumer passes five import/refusal/withdrawal cases; its support-projection withdrawal remains a bounded conformance probe, not an extracted Lean dependency.
- 52 Rust library tests, 30 independent native identity tests, 15 adapter controls and 10 original predicate tests pass. The unchanged bounded Lean theorem compiles axiom-free under its explicit locality/dependency/fingerprint assumptions; it does not prove the native extractor or executable pipeline.

A [supplemental order audit](ordered-input-audit.json), outside the pinned qualification matrix, reordered a genuine two-declaration export to place a referenced definition after its theorem. Rust refused that baseline before issuing evidence; C++ normal/paranoid accepted it. All three refused the changed invalid proof. The result preserves a conservative ordered-input limitation/disagreement and rules out that particular attempted forward-dependency reuse seed; it does not broaden supported inputs or establish general equivalence.

## Trust boundary and retained failures

The native observer uses the existing Rust parser before metadata is discarded. HMAC authority, kernel inference/conversion, the reuse predicate and MathGraph consumer are unchanged. Opting into native identity adds that implementation to the trusted applicability extractor; the captured native binary hash becomes part of authenticated provenance and invalidates incompatible old evidence. Python remains the default and differential oracle.

The independent suites exposed and repaired native acceptance of raw JSON control bytes, ordinary-parser binder metadata drift, bool/int equality conflation in the differential guard, and a shaped refusal followed by a crash incorrectly treated as fallback. An initial memory sampler missed children created from another thread; tracked Popen PIDs and confirmed post-exec executable identity repaired the diagnostic. Raw inherited RSS maxima remain preserved and are not promoted as savings. CI preflight also caught the diagnostic output-directory restriction; superseded run 38881148457 was cancelled and the directory guard repaired.

Two apparently green native CI runs (38879576999 and38881665840) are **withdrawn as qualification evidence**: `tee` masked an original-suite failure caused by appending to a read-only disposable checker. Native/replay/integration failures are retained in [ci-failures.json](ci-failures.json) and decoded-log excerpts. The repair makes only the disposable negative-control copy writable, uses explicit Bash pipefail, separates original qualification, and rejects missing/empty/false correctness reports. A complete nested read-only local run passed 335+197 gates and a new independent replay passed 719 with 21 fresh oracles; source/harness attribution and compressed summaries are retained. The successful economic benchmark observations from the withdrawn runs are not promoted as whole-run acceptance evidence.

## Replay and authority

The [qualification instructions](../../native-qualification.md) reproduce pinned inputs, all full/incremental/negative controls, independent replay, paired economics and the unchanged MathGraph resolver import. Issuer keys remain outside published artifacts; a fresh replay creates its own issuer. The caller must still trust the issuer, extractor, kernel and stated locality/fingerprint assumptions.

[local-qualified.json](local-qualified.json) retains all medians, phase measurements, paired observations, construction subtotals, pins and a content-addressed catalog of compressed complete summaries. Gzip files preserve their original bytes; verify decoded SHA256 using that catalog. The exact [local arithmetic review source](benchmark-review-source.py) is retained with its original explicit workspace paths; it is a snapshot for inspecting that review, while the linked clean-checkout workflow is the portable experiment. The full local MathGraph output remains outside git; its compact copy retains all five outcomes and source pins. CI evidence is recorded separately in ci-qualification.json.

**Highest-leverage remaining UNKNOWN:** safely avoid whole-development identity reconstruction, using authenticated reusable producer/index information while preserving actual changed-byte validation and the existing acceptance boundary. The current native path is a faster full scan, not asymptotically change-proportional verification.
