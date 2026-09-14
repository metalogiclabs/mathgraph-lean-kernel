# MDA Workload Envelope Convergence V3b — Lean Kernel Arena

**Status:** frozen protocol, pre-result  
**Repository:** `metalogiclabs/mathgraph-lean-kernel`  
**Branch:** `mda/workload-envelope-convergence-v3b`  
**Parent experiment:** V3 run `34807040127`  
**Pinned Arena:** `ac1c13762de41b594fa24b90ede8cfd97ac6a765`  
**Frozen workload artifact source:** V3 run `34807040127`, artifact `mda-workload-ground-v3`

## Why V3b exists

V3 established the intended workload pair and same-runner baseline method, but the low masks repeatedly caused GitHub-hosted runners to terminate while `con-leche` was still executing, preventing those cells from writing a final result.

V3b changes only the **measurement envelope** so catastrophic regressions terminate under our control before runner reclamation.

The scientific question and candidate class are unchanged.

## Frozen candidate class

The eight semantically lawful V1 masks:

`[2, 3, 10, 11, 30, 31, 62, 63]`.

## Paired construction and semantic replay

Unchanged from V3.

For every mask:

- GENESIS constructs from `16ccc0ed1c28961e411452d1c1a608761d73929e`;
- SOLVENT constructs from `d6a73279e6765e637f9741180cefbd7ef957d8e5`;
- normalized executable source SHA-256 must agree;
- both constructions must freshly pass:
  - `cargo test --release --locked`;
  - `init-prelude` accept;
  - `extra-rec` reject;
  - `rec-missing-ih` reject;
  - `proj-of-stuck-prop` reject;
  - `proj-of-subst-prop` reject.

## Workload measurements

Each mask is measured against the full present on the same runner for:

- `mathlib`
- `con-leche`

Record:

- wall time;
- user CPU;
- system CPU;
- CPU work = user + system;
- peak RSS;
- exit code;
- timeout status.

## Frozen sufficiency criterion

A candidate is workload-sufficient iff for **both** workloads:

1. it exits successfully;
2. candidate wall time is at most `1.20 * full wall time`;
3. candidate CPU work is at most `1.20 * full CPU work`.

The wall criterion is added explicitly in V3b because repeated V3 runner reclamations show that completion latency itself is an operationally relevant protected consequence.

## Controlled timeout envelope

For each candidate workload, terminate at:

`max(45 seconds, ceil(2.5 * full wall time))`.

This timeout is deliberately looser than the frozen 1.20 wall acceptance boundary. Therefore any timeout is already sufficient to prove **wall-time insufficiency** without needing the candidate to finish.

This avoids the V3 failure mode where catastrophic `con-leche` regressions caused the whole hosted runner to terminate before evidence could be written.

## Frontier

Among workload-sufficient configurations, minimize retained capability count.

V3b passes iff:

1. all eight masks reconstruct from both directions;
2. paired source hashes agree;
3. semantic replay passes;
4. every cell writes a result;
5. a nonempty minimum-cardinality workload-sufficient frontier exists.

## Claim boundary

V3b establishes a bounded same-runner **wall + CPU workload envelope** over Mathlib and con-leche.

It does not establish the official Lean Kernel Arena hardware retired-instruction ranking.
