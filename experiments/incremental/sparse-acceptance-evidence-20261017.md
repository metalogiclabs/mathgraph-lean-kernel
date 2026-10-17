# Sparse issuer-authenticated acceptance receipts — final evidence (2026-10-17)

**WARRANTED_BOUNDED — exact pinned Lean/Std workloads only.** A separate HMAC domain for a baseline-anchored sparse accepted receipt reconstructs precisely the earlier full typed index and checking partition on cold restart, while reducing persisted receipt bytes by 98.83–99.93%. The real source-owned producer, verifier policy, same Rust selected kernel, original accepted baseline HMAC authority, and source-attestation bridge are unchanged. **Three of four predeclared complete-warm-time pairs qualify a speedup; the small unrelated edit is NO_SPEEDUP.**

## Exact source and independent record

- Tested source [3dfc1801ec9e47c724f3b293673462c00ab251a9](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/3dfc1801ec9e47c724f3b293673462c00ab251a9), dedicated [research/incremental-sparse-acceptance-20261017](https://github.com/metalogiclabs/mathgraph-lean-kernel/tree/research/incremental-sparse-acceptance-20261017).
- [Green CI 38983114153](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38983114153), job 117248304797; all required steps passed, including source-identity final gate, original/expanded full-receipt regression, actual kernel and cold sparse acceptance replay.
- [GitHub artifact 12083635111](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38983114153/artifacts/12083635111), independently downloaded ZIP, exact size 2,736,447 bytes and SHA-256 **1dc19c64ac0d5655277a2fc7b142009d6acd7dc698daca9394471adeae14bc94**; matches GitHub-provided artifact digest.
- Original protected 3,436-declaration Lean/Std **243/243 PASS**; expanded 11,653 **226/226 PASS**. All old source-authority controls and new sparse receipt falsifiers passed. Independent native/Python complete typed-index identities, genuine fresh Rust plus official/paranoid C++ oracles and authentic HMAC acceptance audits passed; **no observed unsound acceptance**. Independent cold replay of both real source profiles passed with exact typed witness and checking decision parity.

## Five paired same-host end-to-end warm measurements

The sole intended arm difference is full index acceptance receipt vs sparse authenticated acceptance receipt, with the **same sparse Rust identity wire** in both. Times include source capture, producer, authentication, retained identity, full sealed-composite kernel parser, selected checking and durable receipt persistence. Cold baseline creation is measured outside warm scope; it is not a speedup claim. Per-edit pair order alternates.

| Obligations / edit | Full receipt s | Sparse receipt s | Median savings | Pairs won | Bootstrap 95% ratio interval | Qualified gate |
|---|---:|---:|---:|---:|---|---|
| 3,436 early | 0.223051286 | 0.184416356 | 17.32% | 5/5 | [0.826789, 0.912548] | SPEEDUP |
| 3,436 unrelated | 0.182094558 | 0.163522541 | 10.20% | 4/5 | [0.774918, 1.063453] | **NO_SPEEDUP** |
| 11,653 early | 0.807631181 | 0.682081257 | 15.55% | 5/5 | [0.728497, 0.964659] | SPEEDUP |
| 11,653 unrelated | 0.695016525 | 0.680129785 | 2.14% | 5/5 | [0.771149, 0.996301] | SPEEDUP |

## Actual durable signed record size

| Obligations / edit | Full signed receipt bytes | Sparse signed receipt bytes | Saved |
|---|---:|---:|---:|
| 3,436 early | 4,295,084 | 5,649 | 99.8685% |
| 3,436 unrelated | 4,295,084 | 2,804 | 99.9347% |
| 11,653 early | 20,409,330 | 238,137 | 98.8332% |
| 11,653 unrelated | 20,409,330 | 235,292 | 98.8471% |

Acceptance is a distinct HMAC purpose `mathgraph.incremental-lean.sparse-accepted.v1`, with source-owned transition reference, accepted baseline ID, exact changed export hash, sparse *typed* declaration witness, complete selected obligation set, and immutable provenance. After a cold restart, reauthenticate baseline and reconstruct the complete index; the frozen original reuse predicate must derive exactly the selected set; source-owner transition and actual selected kernel are rerun, not simply accepted based on the HMAC. The full historical receipt remains a conservative fallback for unsupported cases.

## Preserve negative history and explicit residual

Superseded red CI attempts:
- [38982668385](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38982668385) test fixture wrongly treated a conservative global-builtin invalidation as forbidden plus diagnostic text mismatch.
- [38982777873](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38982777873) retained over-restrictive negative test.
- [38982911385](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38982911385) benchmark Python unmatched closing parenthesis.
All these were **harness failures, not accepted bad proofs**; the corrected exact-source run is green. Preserve older source `6e87e4a`/CI `38976918413` qualified sparse *index transport* result separately; do not multiply separate-arm speedups into an unsupported total figure.

**Still UNKNOWN:** asymptotically change-proportional complete verification, formal correctness of source-owned producer/attestation bridge, arbitrary Lean modules or declaration topology changes, and cold-command/lifecycle superiority. Complete parsed-export reconstruction, baseline disk authentication/hash, index expansion in memory and the genuine selected parser still scale with full input size. The smallest next experiment is separately qualified session-owned sealed baseline reuse that avoids per-update mutable-disk rereads, while proving cold restart refuses tampering and actual checker continues using only exact immutable verified bytes. An independent retained kernel parser/session is a later trust-boundary experiment, not yet qualified.

This report is an **evidence-only** descendant of successfully qualified source 3dfc180; its own commit is not represented as CI-tested.
