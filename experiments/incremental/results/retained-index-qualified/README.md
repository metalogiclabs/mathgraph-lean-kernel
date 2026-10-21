# Qualified retained SCC indexing

**WARRANTED_BOUNDED:** authenticated graph-stable warm updates retain the verified index and reclose only changed SCCs and reverse-reachable dependents. Exact fingerprints, dependency witnesses, selected obligations and kernel decisions agree with the qualified full-index implementation. Five paired CI repetitions qualify faster complete warm updates on both pinned real Lean/Std profiles.

Tested source [ef434eb2477fb64d7fd90fdf23f55bd0b35a0243](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/ef434eb2477fb64d7fd90fdf23f55bd0b35a0243), runtime [fa254de](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/fa254deaa7ec5d2881026215de4cfde10866cce4), [branch](https://github.com/metalogiclabs/mathgraph-lean-kernel/tree/research/retained-scc-index-20261016), [successful CI 38961520032](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38961520032), [canonical Research OS](https://app.notion.com/p/3fb3e523d7ab81c68c89c1442eb0bb05). This results-only descendant is not the tested source. The source was frozen on October 16; evidence publication resumed October 21. Later parallel Research OS branches are preserved; this experiment does not supersede them or claim priority.

## Complete warm economics

AMD EPYC 7763, same host, five pairs per edit, alternating adapter-arm order. Rebuilt qualified449, current forced-full and retained adapters use identical actual inputs; direct fresh Rust consumes the identical live sealed full input. Warm update includes producer source capture/elaboration/export, authentication/provenance, identity, genuine selected parsing/checking, full materialization/hash, signing and durable persistence. Cold baseline initialization is measured separately. Direct Rust excludes export generation; this is a conservative comparator.

| Obligations | Edit | Fresh Rust s | Rebuilt449 s | Retained warm s | Less time vs Rust | Less time vs449 |
|---:|---|---:|---:|---:|---:|---:|
| 3,436 | early | 0.273052354 | 0.258597406 | 0.233330862 | 14.55% | 9.77% |
| 3,436 | unrelated | 0.279367364 | 0.230134132 | 0.198308641 | 29.02% | 13.83% |
| 11,653 | early | 1.139220204 | 0.991732757 | 0.882583942 | 22.53% | 11.01% |
| 11,653 | unrelated | 1.144407892 | 0.955715193 | 0.843669542 | 26.28% | 11.72% |

All comparisons above win 5/5; all paired bootstrap 95% ratio intervals lie below 1. Expanded early retained/Rust ratio is 0.774726378 [0.766978940, 0.792577635]; retained/449 is 0.889941303 [0.860238505, 0.913786610]. Expanded early CPU is 0.919536s versus 1.138889s direct Rust and 1.031062s rebuilt449. CPU includes completed children and live-daemon tick deltas; tick granularity limits fine comparisons. Do not compare absolute values with the older Xeon CI run or multiply gains from other branches.

Cold setup and lifecycle are different results. Primary early one-update API component sums, including constructor/start and supported close, are 4.165867169s original and 15.377265020s expanded; neither qualifies a speedup over rebuilt449. Expanded unrelated has a narrow 0.82% lifecycle improvement; the other three lifecycle gates are NO_SPEEDUP. Each matrix arm starts from a fresh session root, so constructor/start includes establishing, fully checking and issuing its baseline. Cold replay is independently accepted, not faster: original setup 3.256813s + replay 0.250110s; expanded 12.110364s + 1.027001s. These single cold observations exclude shutdown and are not fresh source-production measurements. The API permits one baseline-anchored attempt; no multi-update amortization is established. Shutdown uses existing process termination, not measured graceful Rust destructor execution.

## Isolated finish and scaling

The full `finish()` source body remains unchanged. On the expanded early edit, five paired standalone updates measure old core 130.064ms → retained 24.095µs, whole instrumented finish 131.667ms → 29.986µs. Full-mode whole timing includes observation counters; the separately reported core timer covers the unchanged original function. This isolates identity computation from producer, authentication, parsing, JSON/IPC, selected checking and persistence. Four additional seven-pair same-parsed-mutation microbenchmarks preserve complete output parity; expanded early whole finish is 151.391ms → 28.944µs. Clone/reset work is outside isolated timers; baseline preparation is reported separately.

Both 3,436- and 11,653-declaration developments touch exactly three SCCs/declarations/closure hashes and 19 dependency edges for early edits; unrelated edits touch one and 18 edges. Standalone whole finish scales 28.613→29.986µs early and 21.049→21.130µs unrelated. Seven-pair isolated whole timings scale 22.111→28.944µs early and 15.639→21.660µs unrelated. These finite observations and operation counts support local reclosure, not a total asymptotic bound. Complete index roundtrip grows from about 29.8ms to 158.6–170.9ms. Complete warm apply still grows with input size.

Full baseline authentication is now the largest expanded early phase (0.220578s), followed by identity protocol/transfer (0.193637s), complete receipt persistence (0.163807s), selected checking/full parser (0.127679s), and materialization/hash (0.109041s). Phase medians are not additive. Retention increases index-process RSS; post-identity expanded early is approximately 213,380KiB versus 177,652KiB for449. Sampled RSS and startup-inclusive cumulative VmHWM establish neither exact phase peaks nor aggregate memory savings. Detailed CPU, memory, phase and lifecycle samples remain in the archive and machine publication.

## Correctness and authority

CI preserves 197 original, 335 native, 719 independent replay, 251 old benchmark-correctness, 243 original-profile delta and 226 expanded-profile delta gates. The new 181-gate matrix covers 20 pairs × three adapter arms and 40 standalone updates. All complete indexes, dependency witnesses, checked/reused partitions, HMAC receipt audits and independent kernel verdicts agree. Existing MathGraph consumption remains pinned at cf359686c74549a132c7a651cd7aabc7c1a870fe. The old native whole-file adapter remains NO_SPEEDUP.

The 26 independent identity fixtures include edge changes, new/broken cycles, SCC member mutation, unresolved negative keys, restored dependencies, sparse builtin names, axioms, failure poisoning and supplied retained-state refusal. Graph fixtures establish fingerprint behavior, not theorem acceptance. Existing real controls retain forged/foreign deltas, edits outside the reported source region, invalid proofs, axiom/environment/version changes, storage corruption, cold restart and malformed unused DAG rows. Both unused-row forms reach the genuine parser with zero scheduled checks and reject. No qualified negative receives accepted evidence; no soundness mismatch was observed.

Separate independent replay reconstructs ten exact real inputs and executes 40 fresh full checks (current Rust, preserved449 Rust, pinned Lean C++ normal and paranoid) plus eight zero-selected parser checks. [CI input parity](independent-real-replay/ci-input-parity.json) matches their hashes/sizes to the actual CI positives and negatives, including 30 new matrix early snapshots. The package preserves the real tool-hash preflight failure and repaired shared-library invocation failure as execution failures. Compact artifact review itself runs no kernels and cannot reauthenticate historical private HMACs or inspect omitted complete cache witnesses.

The source producer, HMAC issuer authority, verifier policy, conservative reuse predicate, checker inference rules and MathGraph resolver are unchanged. The applicability TCB gains retained transition code; the mode is bound in authenticated provenance. Private retained topology is derived from the authenticated accepted baseline, not imported serialized state. Exact normalized edge preservation is required; graph/global uncertainty uses the existing full-index path, and unsupported metadata/complex changes remain refused under the existing producer policy. Every changed complete input is still actually parsed, including empty selected sets. Arbitrary process-memory corruption is outside this bounded API. The prior bounded Lean theorem does not prove the executable transition or producer-to-verifier bridge.

## Separate sparse-storage negative

After retained-index parity, a subordinate storage capsule experiment ran 20 pairs and 44 intended-cause controls. All eight read/write economic gates are NO_SPEEDUP. Expanded early full receipts shrink 20,409,283→300,273 bytes, but writes cost 1.03644× and cold reads 2.88384×. Both writers pay original complete acceptance signing/content-addressing; sparse adds patch scanning and reconstructs the original accepted envelope before its unchanged HMAC check. Capsules alone grant no acceptance. This representation is not integrated or promoted; later independently qualified sparse-acceptance branches have their own boundary.

## Evidence and replay

- [Machine publication](qualification.json), [strict independent review](ci/independent-review-root.json), [findings](ci/independent-findings.md), [independent arithmetic](ci/independent-economics-review.json), [exact input replay](independent-real-replay/), and actual local red/green/failure evidence are retained.
- [Compact artifact 12075189326](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38961520032/artifacts/12075189326): 37,239,728 bytes; SHA256 `685bb4892c3ceb71a0b23da6159712d72885bc76fbfd13907310b5c41ea7cb13`. Its exact downloaded bytes are committed as [ci/retained-index-summaries.zip](ci/retained-index-summaries.zip). Provider digest, downloaded digest and ZIP CRC checks agree. The strict independent review passes 25,145 checks and 14 fail-closed reviewer falsifiers.
- [Full artifact 12075154855](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38961520032/artifacts/12075154855): provider size 4,210,910,584 and SHA256 `2fcf3e723403d7c34c8e06604607ec0eb69f5a04f82940bb984db9b0840898f0`, expires November 15. The full ZIP was not downloaded or digest-verified. A capped partial remote-read attempt received zero archive bytes and stopped on explicit403; its blocker is preserved. Private issuer keys are intentionally unpublished.

From this directory with repository history available:

```sh
sha256sum -c SHA256SUMS
python3 independent-review/retained-ci-review.py \
  --repo ../../../.. --source ef434eb2477fb64d7fd90fdf23f55bd0b35a0243 \
  --run 38961520032 --job 117177490277 \
  --zip ci/retained-index-summaries.zip --metadata ci/artifacts.json \
  --run-json ci/run.json --jobs-json ci/jobs.json --falsifiers \
  --out /tmp/retained-index-review.json
python3 ci/independent-economics-review.py
```

For fresh executable qualification, check out the exact tested source in a separate worktree and run its SHA-pinned `.github/workflows/incremental-retained-index.yml`, or follow [retained-index.md](../../retained-index.md). Create a new authority outside artifact directories. Independent replay scripts and source recipes in this package require recorded tool bytes or an explicitly recorded fresh qualification; they never silently relax tool provenance.

## Single remaining residual of this qualification

Graph-stable SCC reclosure is local. Complete authenticated verification is still O(total): baseline receipt/export authentication, full-index serialization/IPC, full composite materialization/hash/parsing and complete accepted receipts remain linear. The largest measured remaining phase is baseline authentication. This branch qualifies neither change-proportional total verification nor cold-command superiority; no production deployment, official Arena submission or merge occurred.
