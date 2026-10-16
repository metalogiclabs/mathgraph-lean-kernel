# Qualified authenticated producer deltas

**WARRANTED_BOUNDED:** a warm, baseline-anchored authenticated source update beats direct fresh Rust checking on two pinned real Lean/Std workloads. All five paired early-edit and unrelated-edit comparisons win on the CI host. This qualifies one retained-session transaction, not cold-command or lifecycle superiority.

Exact qualified source: [4496042c75368f6c35675a9b131c960080afa518](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/4496042c75368f6c35675a9b131c960080afa518); [successful exact-source CI](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38945728644); [research branch](https://github.com/metalogiclabs/mathgraph-lean-kernel/tree/research/incremental-producer-delta-20261016); [canonical Research OS](https://app.notion.com/p/3fb3e523d7ab81c68c89c1442eb0bb05). This results-only descendant does not claim that its own HEAD ran qualification. The implementation and reuse/trust boundary are documented in [producer-delta.md](../../producer-delta.md) and [delta-lineage.md](../../delta-lineage.md).

## Actual CI economics

Intel Xeon Platinum 8370C, Linux x86_64; five pairs per case; warm OS cache; fixed update-then-direct order. Direct Rust consumes the **identical live sealed full input** and its timing excludes export generation. The update includes complete application-source capture, genuine Lean elaboration/export, HMAC/provenance and baseline validation, retained identity update, full materialization/hash, actual selected parsing/checking, signing and durable persistence. A new resident baseline session is established for each pair and measured separately. No artificial Python baseline enters these ratios.

| Obligations | Case | Direct Rust seconds | Complete warm update seconds | Time reduction | Speedup | Paired wins | Bootstrap 95% ratio interval |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 3,436 | early-definition | 0.339655 | 0.281331 | 17.17% | 1.207× | 5/5 | [0.80162, 0.84070] |
| 3,436 | unrelated-definition | 0.347932 | 0.241835 | 30.49% | 1.439× | 5/5 | [0.68673, 0.77365] |
| 3,436 | theorem-leaf | 0.328678 | 0.256324 | 22.01% | 1.282× | 5/5 | [0.70254, 0.81521] |
| 3,436 | baseline | 0.334913 | 0.226905 | 32.25% | 1.476× | 5/5 | [0.64976, 0.68305] |
| 11,653 | early-definition | 1.415305 | 1.102488 | 22.10% | 1.284× | 5/5 | [0.73327, 0.82713] |
| 11,653 | unrelated-definition | 1.428212 | 1.128760 | 20.97% | 1.265× | 5/5 | [0.70613, 0.81415] |
| 11,653 | theorem-leaf | 1.406950 | 1.101457 | 21.71% | 1.277× | 5/5 | [0.71964, 0.81345] |
| 11,653 | baseline | 1.458821 | 1.035273 | 29.03% | 1.409× | 5/5 | [0.66011, 0.74506] |

Intervals use 10,000 paired bootstrap samples with seed 20261016. Profiles are separate; this small finite experiment supports no Mathlib extrapolation. Invalid inputs are rejection controls, not claimed repeated economic wins.

Early-edit CPU medians: 3,436 declarations, update **0.281954s** versus direct **0.339201s**; 11,653 declarations, update **1.149598s** versus direct **1.414997s**. Update CPU includes adapter/completed children and live producer/index procfs ticks, whose resolution is `SC_CLK_TCK`. Setup median is **3.879252s** and **14.245238s**, respectively, and is excluded from warm updates. Cold reconstruction/replay is retained separately in the phase evidence; it establishes restart correctness, not a cold speedup.

Phase-separated early-edit medians follow. Phase medians do not necessarily add to the transaction median.

| Obligations | Phase | Wall seconds | CPU seconds |
| ---: | --- | ---: | ---: |
| 3,436 | producer_seconds | 0.024340 | included in end-to-end CPU |
| 3,436 | baseline_validation_seconds | 0.053498 | 0.053476 |
| 3,436 | identity_update_seconds | 0.057704 | 0.060102 |
| 3,436 | materialization_and_hash_seconds | 0.025619 | 0.025623 |
| 3,436 | checking_seconds | 0.065372 | 0.065545 |
| 3,436 | persistence_seconds | 0.044095 | 0.041168 |
| 11,653 | producer_seconds | 0.040989 | included in end-to-end CPU |
| 11,653 | baseline_validation_seconds | 0.237106 | 0.237075 |
| 11,653 | identity_update_seconds | 0.334127 | 0.380927 |
| 11,653 | materialization_and_hash_seconds | 0.097759 | 0.097707 |
| 11,653 | checking_seconds | 0.181447 | 0.181529 |
| 11,653 | persistence_seconds | 0.179433 | 0.172990 |

The expanded early edit independently checks **672 / 11,653** obligations and safely reuses **10,981**; unrelated/leaf edits check 260 and reuse 11,393. The original early edit checks 413 and reuses 3,023. Unchanged updates reuse all. Conservative mutual/complex declaration boundaries remain active. The changed representation is 280 bytes expanded / 271 bytes original; a complete new export is not rewritten to durable storage. The expanded acceptance receipt still contains about 20.4 MB of index data.

## Correctness and independent boundary

The actual CI reports pass **197 original + 335 native + 719 independent replay + 251 benchmark-correctness gates**, followed by **243 original-profile delta + 226 expanded-profile delta gates**. Each delta profile has 21 adversarial controls, five pairs for each of four positive cases, and cold replay. Existing MathGraph receipt integration passes at pinned consumer `cf359686c74549a132c7a651cd7aabc7c1a870fe`. The old native adapter still reports `NO_SPEEDUP`; that negative result is preserved.

Controls cover forged/foreign HMACs; changed bytes outside the announced source patch; source/environment/version/policy drift; signed invalid proofs and axiom changes; actual storage corruption; and unused malformed DAG rows. Both unused-row forms reach the actual parser with zero scheduled declarations and reject. Timeout/protocol failure, an incomplete report or a wrong refusal cause cannot count as a passed control. No qualified negative issues accepted evidence; no soundness mismatch was observed.

Fresh full Rust, Lean C++ and paranoid C++ checks are independent acceptance/rejection oracles. Full native and original Python indexes agree with pinned ordinary exports and complete dependency witnesses. A separate replay helper reconstructs the expanded positive and four invalid composites without invoking the incremental engine, runs 15 fresh full kernel commands plus two zero-selection parser commands, and checks original-c5 index parity. It was executed twice locally. [CI input parity](ci/independent-kernel-input-parity.json) binds these exact five input hashes to CI; C++ executable hashes also match, while Rust/producer/index executables differ across builds. Compact reports do not independently attest the remote machine or reauthenticate its private HMAC key.

The HMAC issuer, verifier policy, kernel inference/conversion rules, conservative reuse predicate and MathGraph resolver are unchanged. The applicability TCB gains the source-owned producer, complete-source attestation bridge and retained delta decoder. Source attestation never grants kernel acceptance. The existing bounded Lean theorem does **not** prove this executable bridge.

## Preserved evidence and replay

- [Machine-readable publication](qualification.json), [CI job/log review](ci/independent-ci-log-review.json), [compact archive review](ci/independent-compact-review.json), per-profile independent reviews and input parity accompany the exact archive.
- [Compact CI artifact](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38945728644/artifacts/12067972795): **4,289,544 bytes**, SHA256 `961abb3e6834443dab2cc86eedaf27420c41f52b50d5cbe6c28455ddbd8f2ea5`. Its downloaded bytes are committed as [ci/ci-4496042-summaries.zip](ci/ci-4496042-summaries.zip), including original reports and phase samples. Provider digest and downloaded digest match.
- [Full CI artifact](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38945728644/artifacts/12067792895): **2,174,807,684 bytes**, provider SHA256 `a2fa6f111a5bf26178226eb357931856f83c548a983b42602a294e64d2915811`. It contains full caches/commands/input evidence. The full ZIP was not independently downloaded through the connector's 512 MiB limit; no downloaded full-ZIP digest check is claimed. Actions retention expires 2026-11-15; committed reports, pins, helpers and representative raw independent logs remain after expiry.
- Local full-file reviews and compressed complete summaries are preserved separately from CI. Their helper audits read retained results/configs/logs and recompute partitions/economics; eight falsifiers fail closed. CI compact review checks archive integrity, source/binary provenance, completeness and arithmetic, but cannot read omitted complete caches/results. Its own 13 falsifiers fail closed.
- [CI failures](ci-failures.json), [development failures](development-failures.json), actual failed logs and original native negative economics retain causal history. No earlier withdrawn green run is reinstated.

From this directory, with the repository history available:

```sh
sha256sum -c SHA256SUMS
python3 review-compact-ci.py --zip ci/ci-4496042-summaries.zip \
  --metadata ci/compact-artifact-metadata.json --repo ../../../.. \
  --source 4496042c75368f6c35675a9b131c960080afa518 --out /tmp/producer-delta-archive-review.json
unzip ci/ci-4496042-summaries.zip -d /tmp/producer-delta-ci
python3 review-evidence.py --summary /tmp/producer-delta-ci/delta-expanded-qualification/summary.json \
  --expected-source 4496042c75368f6c35675a9b131c960080afa518 --source-root ../../../.. \
  --falsifiers --out /tmp/producer-delta-summary-review.json
```

For a fresh executable qualification, check out the exact source in a separate worktree and follow [producer-delta.md](../../producer-delta.md), or dispatch its pinned workflow. Create a new authority key outside output directories; historical issuer keys are intentionally unpublished. The portable `replay-delta-evidence.py --help` explains full-artifact path rebasing and recorded binary-hash requirements. It verifies kernels and indexes without an issuer secret; it does not claim to authenticate old private HMACs. Its actual local invocation, summaries and stdout/stderr are committed here. Byte-identical reproduction of a recorded executable remains a requirement when replaying its tool pin; a fresh qualification records newly built pins instead.

## Remaining UNKNOWN

This removes full expression-DAG identity reconstruction and durable full-export rewriting. It is **not asymptotically change proportional**: complete declaration SCC/reclosure and index serialization, baseline receipt authentication and export hashing, full memfd materialization/hash, full actual parser restoration and complete-index receipt persistence remain O(total development). Expanded early identity update is the largest measured wall phase (**0.334127s**, CPU **0.380927s**), followed by baseline validation (**0.237106s**). The next smallest unresolved residual is authenticated retained declaration-closure/index maintenance without full SCC/index serialization. Do not change the reuse rule to remove that cost without new locality evidence.

Producer hash-table COW may copy retained capacity. Memory evidence consists of post-phase per-process RSS and cumulative VmHWM samples; it establishes neither exact phase peaks nor aggregate memory savings. Arbitrary revision streams, universal ordinary-export parity, general source mutations, cold-command superiority and a formal producer-to-verifier bridge remain UNKNOWN. No production deployment or official submission occurred.
