# Qualified retained receipt-index comparison

Exact source: [`5dfe38b01ca7b1c67f70be4ffb2479978049239e`](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/5dfe38b01ca7b1c67f70be4ffb2479978049239e).
Branch: [research/incremental-retained-continuation-20261021](https://github.com/metalogiclabs/mathgraph-lean-kernel/tree/research/incremental-retained-continuation-20261021).
Qualification: [successful run 39581949051](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/39581949051), job 119161428100, completed 2026-10-21T11:11:57Z.

**WARRANTED:** on the pinned genuine Lean 4.35.0 / Std developments, the complete warm authenticated producer-to-persisted-receipt path beats same-input fresh full Rust on all four primary five-pair cases. All verification decisions agree with the qualified full-index implementation and independent full Rust/C++/paranoid checks. This is a bounded warm result, not a formal proof of the executable bridge or change-proportional total work.

## Measured economics

Wall medians below are milliseconds. Each row uses five alternating pairs, with every arm separately compared against a fresh full Rust process on its identical live sealed export. All four new-versus-canonical and new-versus-direct-Rust gates have 5/5 wins and pointwise bootstrap 95% ratio upper bounds below 1. These are same-host repeated observations, not simultaneous/familywise or cross-host confidence guarantees.

| Obligations / edit | Prior canonical comparison | New shared comparison | New vs prior saving | Direct fresh Rust | New vs Rust saving | Rust/new |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 3,436 / early-definition | 164.907 | 135.640 | 17.75% | 284.934 | 52.40% | 2.101x |
| 3,436 / unrelated-definition | 130.641 | 103.014 | 21.15% | 278.595 | 63.02% | 2.704x |
| 11,653 / early-definition | 419.135 | 401.830 | 4.13% | 1183.929 | 66.06% | 2.946x |
| 11,653 / unrelated-definition | 503.092 | 260.504 | 48.22% | 1174.352 | 77.82% | 4.508x |

Warm CPU canonical→shared medians: original early 163.557→136.012ms, original unrelated 125.323→97.898ms; expanded early 422.555→399.637ms, expanded unrelated 514.715→280.744ms. All four CPU gates pass. Full raw pairs, phase durations, seeds, intervals and resource observations are in the exact ZIP; [metrics.json](metrics.json) presents the measured values. [ci/independent-economics.json](ci/independent-economics.json) independently recomputes all 28 scoped comparisons without importing project verification code.

Cold initialization remains expensive. The shared arms’ fresh-baseline setup medians are 4.059/4.074s on the original early/unrelated cases and 15.213/15.154s expanded. Setup-plus-one-apply component medians are 4.193/4.173s and 15.557/15.422s, much slower than a single direct Rust check. Against the prior equality mode, only original-early setup+apply has a marginal 0.695% SPEEDUP; the other three remain NO_SPEEDUP. These component sums exclude shutdown and independent oracles. No multi-update amortization is qualified. Four actual cold replays reauthenticate prior evidence and repeat the same decisions; they do not claim a new full baseline check. Cold shared setup/apply observations are 3.550906s/0.116808s original and 12.724238s/0.403724s expanded, one observation each.

Procfs memory observations retain post-phase RSS and cumulative startup-inclusive VmHWM, including benchmark/oracle reference state. Missing exited processes and absent cold producer measurements remain missing. Expanded adapter RSS observations can increase (about616→664MiB early and620→666MiB unrelated); no total or phase peak-memory improvement is claimed.

## Small runtime change and trust boundary

The base is the existing actual retained-parser admission source6e71704, following already implemented retained SCC transition, sparse index transport, signed sparse acceptance and admitted immutable baseline. No checker, Rust parser, identity/dependency engine, source producer, HMAC authority, reuse predicate or MathGraph resolver is rebuilt here.

The unchanged sparse authenticator still verifies HMAC/content address, reconstructs the full index and independently reapplies the same conservative reuse rule. Only its final reconstructed-versus-live index comparison changes from two complete canonical encodings to exact JSON comparison that skips shared private baseline subtrees. Mixed/unsupported types, floats and Unicode aliases fall back to the old encoder. Comparison mode enters signed producer provenance; opposite-mode cold restarts refuse without writing acceptance evidence.

No logical authority is added by this optimization. The existing private trusted-process/admitted-baseline boundary remains. The inherited retained native parser is an additional semantic TCB: it checks baseline+delta AST while a separate materializer builds the complete sealed export. The finite independent oracle tests cover their correspondence here; neither the old Lean bounded model nor this comparator’s differential tests prove that executable bridge.

## Correctness, controls and independent replay

- Exact-source CI preserves all 197 original, 335 native identity/adapter, 719 independent replay/full-kernel and 251 original-binary gates, plus 246 original and 229 expanded protected gates. All pass; the old 251 economic NO_SPEEDUP is preserved separately. Each protected profile has 21 actual negative controls and 21 positive/cold samples.
- Forged or wrong-domain attestations, unreported source changes, false names, import/environment/version drift, foreign authority, corrupted baseline/receipt/genesis/delta/transition/representation storage and cold restart are checked. Invalid proofs, changed axiom fixtures and malformed unused DAG rows have separate retained and full oracle outcomes. Zero selected declarations still parse changed bytes. A retained axiom/overwrite refusal is a conservative policy refusal, not proof of a mathematical rejection.
- Retained parser shadow comparisons preserve five pairs on each profile/edit and four malformed-unused/old-expression-overwrite negative controls.
- New comparison: 20 paired trials across four cases, 40 actual warm arms, 4 cold replays and 4 bidirectional cross-mode refusal controls. Every arm has actual selected checking, same-input fresh Rust acceptance, fresh full native index, independent applicability partition and actual issuer HMAC/content-address audit. First pairs also run C++/paranoid and Python/native index differential checks.
- The portable independent artifact reviewer passes 15,067 checks and 40 falsifiers, reconstructing all 8 representative baseline+delta exports, typed indexes, complete decisions, receipts and raw checker/config/output identities. It imports no incremental engine/controller. Historical secret HMACs are observed from the actual issuer harness, not independently reauthenticated without private keys.
- Separate fresh replay runs 74 real processes using current Rust, preserved449 Rust, normal/paranoid C++ and direct retained/fresh-selected parsers. Actual CI input parity has 74 exact SHA+size matches, 0 missing and 0 mismatched. Two extra local overwrite-policy cases and unreplayed baseline/leaf samples are explicitly separated. No timeout or loader failure counts as rejection.
- Independent comparison differential: 1,604 adversarial cases in both directions, including all 8 real index shapes. Arbitrary cyclic/deep/custom Python graphs are outside the admitted native JSON schema.

Independent reviewer failures are preserved: v1 confused cold prior authentication with a new full baseline check and assumed no missing process sample. V2 then rejected the actual cold producer phase=None. V3 permits only that absent cold producer phase, retains all other phase observations, and preserves all acceptance/provenance/economic gates. Frozen versions, RED logs and GREEN/falsifier results remain in independent-review/. The product source never changed during these reader repairs.

## Immutable artifacts and replay

Compact [artifact12342450124](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/39581949051/artifacts/12342450124) is preserved byte-for-byte as [ci-compact.zip](ci-compact.zip): 58,533,476 bytes, SHA256 `7aa231dff8ddda4d1f6cbd073d62ea408ac5e8f491f421f1ceeebfa5a01f4847`, 180 CRC-valid members. The archive holds 279,277,822 uncompressed bytes. Provider/native run/jobs/artifact metadata and decoded log hashes are in ci/.

Full [artifact12342135278](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/39581949051/artifacts/12342135278) is 3,187,925,325 bytes with provider SHA256 `c2c43ed69e1f279ea4fddd6bfc32ddc8ea90e80eb7ac067d3aebd04a3f79af30`. It was not downloaded or independently byte-hashed here because it exceeds the available local volume. Do not confuse its provider digest with the compact archive’s verified digest. Both provider artifacts expire 2026-11-20; the committed compact bytes and representative inputs remain replayable.

Run `sha256sum -c SHA256SUMS` and `bash replay-evidence.sh /absolute/path/to/fresh-review-output` from this directory in a clone containing exact source 5dfe. This verifies archive/provider/source associations, reconstructs all representative bytes/decisions, recomputes economics, runs falsifiers and compares fresh replay input identities. It executes no kernel and makes no acceptance certificate. For fresh kernel replay, use independent-kernels/README.md and its portable pinned-baseline/delta reconstruction recipes, plus the exact source workflow/setup commands. Re-running full qualification creates a fresh private HMAC authority rather than publishing the historical issuer key.

The diagnostic archive retains exact predecessor6e CI evidence, its early-edit NO_SPEEDUP results, links to the earlier [red fixture run](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38995019800) lineage, local RED/GREEN and instrumented profiles. Local profiles and one-pair smoke retain dirty-source metadata and are not promoted as exact-source five-pair qualification.

## Remaining residual

Full index reconstruction in the cold receipt authenticator, the repeated applicability scan, declaration-list comparison, source/session initialization and complete sealed-export materialization/hash remain linear. Expanded materialization/hash is the largest stable named warm phase: 113.459ms early and113.723ms unrelated. This result does not establish asymptotic change proportionality.

The next profiling UNKNOWN is the cause of variable unpartitioned API time in expanded early edits (two shared samples have142.724ms and145.975ms outside the six reported phases). The raw timing residual is preserved; garbage collection or another cause has not been established. Phase medians must not be summed into a causal explanation for the complete warm median.
