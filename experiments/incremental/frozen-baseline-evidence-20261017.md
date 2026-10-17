# Session-owned immutable verified baseline — final bounded qualification (17 October 2026)

**WARRANTED_BOUNDED:** Retain exact issuer-authenticated Python immutable source bytes for the lifetime of one source-owner warm session. Warm updates need not reopen or rehash mutable baseline storage; a cold restart must reauthenticate that storage. This is not an OS-sealed memfd or a proof against compromise of the trusted process.

## Exact source and independently inspected evidence
- **CI-qualified source:** [f02c02d5c87c2e6e31774a746557829b2d27b6c4](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/f02c02d5c87c2e6e31774a746557829b2d27b6c4).
- [Green CI #38986502657](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38986502657), job 117259105386; all job stages green.
- [Artifact #12084212664](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38986502657/artifacts/12084212664), 2,738,205 bytes, downloaded, independently SHA-256 **1754d60a3b09de2345db8c8f9e57795102c505a11cd22e609aa2ca96801a4a79**, matches provider digest. Contains `legacy-original/summary.json`, `legacy-expanded/summary.json`, `frozen-baseline-ab/summary.json` and markdown summaries.
- **All 243/243 small and 226/226 expanded regression gates passed**. Original source-owned producer, signed baseline, sparse index wire, HMAC sparse receipt, existing applicability predicate, selected Rust checker, and actual Rust/C++/paranoid full-kernel oracles unchanged. The two independent all-input identity oracles and actual checked-obligation decisions agreed exactly.
- On each real Lean/Std profile the **warm post-admission durable corruption** control passed: a mutated cache file could not change the already-admitted immutable bytes actually checked by the running session. A separate cold session rejected the corrupt durable file; after exact byte restoration a fresh source-owned cold replay reproduced the previous accepted receipt. All cold replays passed. Initial session hashes and compares the pinned Lean-source export to authenticated evidence; no mutable disk can replace the already admitted in-process bytes.

## Causal five-pair warm producer-to-durable-persistence timing

| Obligations / edit | Durable baseline rehash (s) | Immutable session snapshot (s) | Saving | Wins | Bootstrap 95% ratio | Gate |
|---|---:|---:|---:|---:|---|---|
| 3,436 early | 0.199774 | 0.154857 | **22.48%** | 5/5 | [0.74459, 0.78326] | SPEEDUP |
| 3,436 unrelated | 0.171610 | 0.120548 | **29.75%** | 5/5 | [0.64567, 0.74151] | SPEEDUP |
| 11,653 early | 0.803784 | 0.465349 | **42.11%** | 5/5 | [0.57796, 0.65874] | SPEEDUP |
| 11,653 unrelated | 0.757151 | 0.562883 | **25.66%** | 5/5 | [0.55794, 0.88743] | SPEEDUP |

**Identity of cost removed:** per-update baseline validation ~0.0456s (small) and ~0.204–0.214s (expanded) becomes ~0.0001s retained warm check. Complete cold/session startup is excluded: original roughly 3.89s, expanded roughly 14.7–14.9s. Independent per-source, per-host finite warm comparisons only; bootstrap interval is not universal evidence. This is measured **against durable rehash with the exact same sparse receipt, sparse identity wire and verifier**, not direct fresh Rust head-to-head; do not claim a new fresh-Rust speedup percentage or multiply unrelated experiment gains.

## Negative history, boundaries and next residual

The operating trust boundary is the issuer process + immutable Python bytes admitted after genuine baseline source and HMAC checks. This is not a formally verified program. The in-memory snapshot is a historical proof-input identity, not a live check that disk is still current. If a user changes durable disk while the live session runs, **proof of the admitted immutable snapshot remains**, while durable-present freshness is UNKNOWN until reauthenticated. A cold restart always checks fresh durable bytes and source attestation.

Remaining **UNKNOWN**: general Lean modules/topology changes, full-input parser/memfd export materialization, in-memory index/dependency scan and long-lived multiple consecutive updates, amortized lifetime economics and unproven source-producer/bridge. The next decisive experiment should isolate the independent Rust checker’s full-export parse costs and determine whether a retained parser could stay sound under authenticated source delta and still reject unused malformed bytes. Do not skip parser validation of changed bytes or treat the HMAC witness as a kernel verdict.

This document is evidence-only; its own descendant HEAD is not claimed to have passed CI.
