# Authenticated accepted-predecessor lifecycle qualification

Source: [`d1b22447d23a928ae536cbe838a47fc9682a4b39`](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/d1b22447d23a928ae536cbe838a47fc9682a4b39). Branch: [research/incremental-revision-lifecycle-20261022](https://github.com/metalogiclabs/mathgraph-lean-kernel/tree/research/incremental-revision-lifecycle-20261022). Exact-source [CI 39679768047](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/39679768047), job 119498882697, completed successfully on 2026-10-22. Evidence provenance is the commit introducing this directory; its exact SHA is recorded in the [canonical Research OS checkpoint](https://app.notion.com/p/3fb3e523d7ab81c68c89c1442eb0bb05) and final delivery.

## Result and scope

**WARRANTED:** the existing MathGraph incremental checker can carry accepted evidence through forty successive controlled changes, including cumulative edits and restorations, while its complete measured lifecycle beats direct fresh Rust verification of the same actual exports. This includes genuine genesis checking, constructor/start, source production, authentication, identity update, actual selected checking, receipt/head persistence and supported shutdown.

The pinned real Lean 4.35.0/Std workloads contain 3,436 and 11,653 obligations. Each of five paired sequences makes ten four-step cycles: early edit; unrelated edit retaining the early edit; early restoration retaining the unrelated edit; unrelated restoration. Each acceptance names its immediate accepted predecessor. These are continuing revisions, rather than forty independent forks from genesis. This extends the prior qualified warm-only result; it does not replace that stronger per-edit warm evidence with lifecycle averages.

## Measured economics

The primary comparison is a separately timed uninterrupted incremental lifecycle against forty-one fresh Rust processes on genesis and the same forty sealed revision exports. Direct input preparation occurs before its timer, favoring direct Rust. Arm order alternates over five pairs. Qualification oracles and evidence packaging occur outside both primary intervals.

| Obligations | Fresh Rust lifecycle median | Incremental lifecycle median | Wall reduction | Rust/incremental |
| --- | ---: | ---: | ---: | ---: |
|3,436|11.371610s|8.080982s|28.9372%|1.40721x|
|11,653|54.792482s|33.506680s|38.8480%|1.63527x|

Both profiles win 5/5 pairs. The pointwise paired-bootstrap 95% candidate/direct ratio intervals are [0.599858,0.711717] and [0.545923,0.619720], respectively, using 10,000 resamples. The reported ratio is the ratio of arm medians, not the median of five per-pair ratios. These are repeated same-host observations with warm OS caches, not cross-host or simultaneous confidence guarantees.

Continuous CPU medians are 11.374423→8.078343s (28.9780% reduction) and 54.792057→33.563868s (38.7432%). Separate interleaved API component sums are 11.803732→8.250252s and 53.281320→31.043097s. Component sums and phase medians are not substitutes for the primary uninterrupted wall measurement.

Fresh genesis/start API wall medians within the continuous arms are 3.753791s original and 14.935065s expanded. Forty accepted-update API sums have medians 3.993971s and 17.788029s. These are separately summarized quantities; adding their medians does not reconstruct a lifecycle median. The primary outer timer also includes constructor, close and compact recording.

Warm continuous per-edit API medians, pooled descriptively over 50 observations per edit, are 112.042ms early /75.509ms unrelated original and 499.148ms /472.530ms expanded. Interleaved same-input fresh Rust command medians are 289.584/288.308ms and 1297.726/1279.427ms. These separately observed warm medians are contextual, not a replacement paired speedup qualification.

Separate final forty-step expected-head recovery takes 8.087556s setup and 0.054940s close original; 32.818418s setup and 0.120544s close expanded. Independent snapshot/index checks occur between those components, so their sum is not an uninterrupted cold elapsed measurement. Recovery authenticates prior genesis acceptance and genuinely replays accepted revisions; it does not claim a new full genesis check. There is one recovery observation per profile, with logically cold retained processes and warm OS caches, excluded from primary lifecycle economics. Actual lifecycle observations qualify forty updates; there is no projected crossover claim for other history lengths.

[Phase analysis](phases/actual-ci/analysis.json) uses exact arithmetic on the original published ZIP. Expanded pooled update time is 42.999% persistence, 22.724% complete materialization/hash and 2.127% identity. Corresponding original shares are 23.754%, 26.014% and 2.016%. Promotion is nested within persistence and must not be counted again. Native finish still includes full index cloning/all-component root advancement, so it is not pure affected-cone time. No cause is assigned to residual gaps.

One forty-update original sequence authenticates 4,764 delta bytes while materializing/hashing 636,892,477 complete-export bytes; expanded authenticates 4,795 delta bytes while materializing/hashing 2,564,646,194 bytes. Promotion reads the entire successor again inside persistence. Complete export disk writes are zero for these updates, but sealed memfd writes, hashing, baseline IO and small durable objects still occur. This byte accounting makes the remaining linear work explicit.

Post-phase memory observations are RSS and cumulative VmHWM from the interleaved arm, which also contains oracle/reference state. Missing exited processes are missing measurements. The uninterrupted arms have no continuous aggregate peak-memory measurement; no aggregate peak-memory saving is claimed. Selected checking differs between profiles (early/unrelated 413/1 versus 672/260), so these two workload sizes do not establish constant affected-cone scaling.

## Implementation and trust boundary

`RevisionChainSession` retains the existing producer/exporter, native graph/SCC state and genuine Rust parser after each accepted revision. Versioned chain heads bind the immediate parent head and evidence, revision number, complete bounded source capture, exact delta/export identities and producer policy. Source capture covers all six pinned application files; the actual producer compares the complete local environment. Reported names and patches are assertions, not authority.

The HMAC issuer/key model, verifier policy, conservative applicability predicate, genuine checker and MathGraph resolver remain in use. The new versioned state-continuation implementation is additional trusted code. Acceptance promotes source/export/layout/index/receipt/head only after checking and persistence. Any failure poisons the live processes. A receipt orphaned by later persistence failure is historical evidence, not an accepted successor head. Changed DAG rows still pass through the genuine parser when selected checking is empty.

Cold recovery authenticates all referenced objects and reproduces source/delta history from genesis before reinstating historical authenticated envelopes. The caller must supply an externally retained expected head. HMAC authenticates a historical prefix; it provides no generic latestness or rollback service. Current rejected or UNKNOWN source does not inherit historical current acceptance. Semantic restoration may retain unused appended DAG rows and need not restore the original export SHA.

The source/export/parser/identity executable bridge remains an explicit trust assumption tested by finite differential controls. No whole-pipeline formal proof is claimed. Content hashes identify bytes under their cryptographic assumptions; they do not prove semantic equivalence.

## Correctness and negative controls

- Exact-source CI preserves all 197 original, 335 native, 719 independent replay/full-kernel and 251 original-binary gates, plus 246 original and 229 expanded protected gates. The old 251 economic NO_SPEEDUP remains separate from its passing correctness gates.
- There are 32 new chain/recovery/adversarial controls per profile, 64 total. They include forged HMACs, changed unauthenticated deltas, altered source captures, wrong parents, environment/version drift, source modifications outside the reported region, false name hints, axiom/kind changes, invalid source proofs, foreign issuers and policy mismatch.
- Storage controls cover head, source capture, current receipt, transition, delta, representation, genesis, baseline receipt and baseline export corruption; missing latest heads cannot fall back to an older prefix. Persistence failure cannot promote a head. Recovery after refusals and real dependency-edge fallback/restoration are checked against the full-index path and fresh Rust.
- Two actual kernel-negative exports per profile exercise malformed unused DAG bytes at zero selected obligations and an authenticated invalid definition proof. Retained, fresh Rust, normal C++ and paranoid C++ must reject with an actual rejection exit. Policy refusal/UNKNOWN is distinct from mathematical kernel rejection; no timeout, unsupported input or loader failure counts as rejection.
- All 400 interleaved accepted revision decisions have exact full-index/fingerprint/partition parity and fresh full Rust agreement; representative states also receive Python-index, C++ and paranoid checks. The separate continuous arms bind every actual export and acceptance to those independent witnesses. The independent stdlib artifact reader passes on the exact original ZIP: 10 paired interleaved lifetimes, 400 accepted revisions, 3,017,800 per-declaration decisions, 2,440 signed-object links and 448 compressed archives. It independently recomputes all 88 economic series and 880,000 bootstrap resamples. Four hundred additional continuous revision receipts are bound to the interleaved full-index/kernel audit. The reader imports no incremental engine, producer controller or project benchmark. It enumerates 16 unique exact inputs, 12 accepted and 4 rejected, for separate kernel replay; its own result explicitly says that it runs no fresh kernel. Both exact 32-control matrices pass. The declaration-own-hash/export bridge remains the frozen full-native/Python witness, rather than an independently proved parser bridge.
- All five actual-artifact falsifiers refuse in memory: fake zero-work success, missing complete input, changed compressed-input identity, raw parent substitution and omitted changed-input coverage. The frozen reader files and qualified source remain unchanged throughout; there are no actual-artifact reader repairs. See [independent assessment](independent-review/actual-ci/assessment.json) and [falsifiers](independent-review/actual-ci/falsifiers.json). Compact topology controls omit the prior step2 receipt: that first parent is checked by identifier and all decision origins; subsequent links are exact. The main 400-step audit is separate and complete.
- Separate [fresh replay](fresh-kernels/summary.json) executes 48 real Rust/C++/paranoid processes over 16 (12 accepted and 4 rejected) exact published inputs; all three oracles accept every one of the 12 accepted inputs and reject every one of the 4 invalid inputs with exact exit codes 0/1. There are no timeouts, unsupported verdicts or checker failures. Input bytes and executed binaries remain unchanged before/after checking. This replay invokes independently fresh full Rust, pinned normal C++ and pinned paranoid C++ without importing the incremental engine or cache authority. Rust is locally built from exact qualified source; historical CI Rust executable-byte equality is not assumed. Historical secret HMACs are observed through issuer-audit witnesses, not publicly reauthenticated without the private CI key.

## Artifacts and replay

Compact [artifact 12390854795](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/39679768047/artifacts/12390854795): 1,250,298,163 bytes, provider SHA256 `878fbeeb4f6241084fd89ca20a2b9b8077c9071e2ada7e2e0b94d054e743d766`. The reconstructed local original ZIP has the exact provider size and SHA256; all 9,482 member CRCs pass. Eleven ordered lossless XZ parts are listed in [packaging/manifest.json](packaging/manifest.json), each at most 48 MiB. Their concatenation is 528,312,196 bytes, SHA256 `a78f2817c3f6f8c1eca9c50dc851baa2a9f5bf9d92329378114a2cca2df9fd13`. Separate root reconstruction from the copied preservation parts verifies every part, writes and rehashes the original ZIP, and checks every member CRC; see [root preservation proof](packaging/root-reconstruction-proof.json). This packaging is storage/transport only; compression is not runtime performance evidence.

Full [artifact 12391188911](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/39679768047/artifacts/12391188911): 4,486,141,109 bytes, provider SHA256 `dbb4e7819ddfe1c07f4dd4fbeb98fa2005d6cfaab8b66d8b8dfe4ea54a1714d7`. It was not downloaded or independently byte-hashed here. Keep provider metadata distinct from locally verified compact bytes.

Transport issue: this workspace's proxy refused the native blob redirect and the GitHub connector rejected the compact archive above its 512 MiB limit. A separate transport-only CI run [CI 39698586368](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/39698586368), source `3ec0191126fa0f544fadec05435c02ac2be0c8aa`, split the exact published ZIP, without rerunning qualification or changing its source. Reconstructed compact bytes must match the original provider digest. Preserve the transport manifest, part digests and run metadata.

The executable [replay-evidence.sh](replay-evidence.sh) performs reconstruction, exact-source review, directed falsifiers, all fresh kernels and phase arithmetic. Supply a fresh absolute output directory and the three pinned/exact-source checker paths. It creates a detached runtime worktree. Reconstruction writes a 1.25 GB ZIP; the full audit decodes a 344 MB summary. Historical local reviewer unit tests retain their original smoke-fixture paths; those development logs are lineage, while the actual-artifact replay uses only the committed archive and source.

Replay manually from a clone containing the evidence and exact source:

1. Verify `SHA256SUMS`, then reconstruct the exact compact ZIP from ordered parts. Choose an existing output parent directory and a fresh output file:

   ```sh
   python3 packaging/reconstruct_archive.py --manifest packaging/manifest.json \
     --output /fresh/output/ci-compact.zip
   ```

   The helper verifies all part sizes/digests, concatenated XZ size/digest, original ZIP size/digest, written output bytes and every ZIP member CRC. See [packaging/README.md](packaging/README.md).
2. Create a detached worktree at `d1b22447d23a928ae536cbe838a47fc9682a4b39`; do not run source-bound replay from the later evidence commit.
3. Run the preserved independent stdlib reader on the archive with expected source and observed CI provenance. It must reconstruct receipt/parent linkage, reuse partitions and raw input coverage without importing the incremental controller, then recompute economics and run its falsifiers.

   ```sh
   python3 independent-review/reviewer.py --artifact /absolute/path/to/ci-compact.zip \
     --repo /absolute/path/to/detached-runtime-source \
     --source d1b22447d23a928ae536cbe838a47fc9682a4b39 --output /fresh/output/review/ci-review.json
   python3 independent-review/run_falsifiers.py --artifact /absolute/path/to/ci-compact.zip \
     --repo /absolute/path/to/detached-runtime-source \
     --source d1b22447d23a928ae536cbe838a47fc9682a4b39 --output /fresh/output/review/falsifiers.json
   ```
4. Run the preserved `fresh_kernel_replay.py` using the reader's newly generated `inputs.json`, exact Rust build and pinned normal/paranoid C++ kernels. It must check every actual input digest before and after all three genuine kernel processes.

   ```sh
   python3 independent-review/fresh_kernel_replay.py --artifact /absolute/path/to/ci-compact.zip \
     --inputs /fresh/output/review/inputs.json --repo /absolute/path/to/detached-runtime-source \
     --source d1b22447d23a928ae536cbe838a47fc9682a4b39 \
     --rust /absolute/path/to/exact-runtime/release/sokonanoda \
     --cpp /absolute/path/to/lean-4.35.0/bin/leanchecker \
     --paranoid /absolute/path/to/lean-4.35.0/bin/leanchecker-paranoid --out /fresh/output/kernels
   ```

   Build Rust with `cargo +1.95.0 build --release --locked --bin sokonanoda` in the detached runtime source. Use the pinned toolchain/binary setup in that source's `experiments/incremental/setup.sh`; the replay script checks normal/paranoid executable SHA256 against exact `pins.json`. The replay output directory must not already exist.
5. For a new full qualification, use the exact-source workflow/setup commands. A fresh run creates its own private HMAC authority; the historical issuer key is not published.

Preserve source/binary hashes, raw paired measurements, independent reader source/tests/RED repairs/falsifiers, fresh-kernel configs/logs/input hashes, phase analysis, metadata and ROS readback proof. Do not silently replace actual historical failures with later summaries.

## Remaining residual

Per-update complete export materialization/hash, full successor readback, full index cloning and remaining declaration/receipt scans still scale with total development size. Cold recovery scales with accepted history. **UNKNOWN:** how to remove those full-development costs while preserving the same authenticated source-to-export integrity and independently checkable acceptance boundary. The qualified lifecycle speedup is bounded and concrete; total verification is not yet asymptotically proportional only to the affected dependency cone.

## Research authority and publication

The [canonical Research OS checkpoint](https://app.notion.com/p/3fb3e523d7ab81c68c89c1442eb0bb05) is synchronized and read back. Its previous 81,733-byte body remains an exact suffix; see [sync proof](ros/readback-proof.json). [Published evidence readback](published-readback/assessment.json) confirms every original evidence Git blob identity and independently decoded critical report bytes at `d5aa24cc52f6a38c79d097be58226547181cc97b`. This subsequent metadata commit changes no qualified runtime code.
