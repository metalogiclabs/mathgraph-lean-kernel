# MDA Bidirectional Convergence V1 — Lean Kernel Arena

**Status:** frozen protocol, pre-result  
**Repository:** `metalogiclabs/mathgraph-lean-kernel`  
**Branch:** `mda/bidirectional-convergence-v1`  
**Starting full present:** `d6a73279e6765e637f9741180cefbd7ef957d8e5`  
**Genesis base:** `16ccc0ed1c28961e411452d1c1a608761d73929e`  
**Pinned Arena:** `ac1c13762de41b594fa24b90ede8cfd97ac6a765`

## Question

Within the frozen six-capability continuation class already defined by the MathGraph MDA domain pack, do opposite developmental directions recover the same minimal semantically sufficient frontier?

- **GENESIS:** start below the retained capability sequence and add selected capabilities.
- **SOLVENT:** start from the full accepted present and contract the complementary capabilities.

The test is deliberately configuration-level:

> **Minimality is over configurations, not individually indispensable components.**

## Capability atoms

| Bit | Commit | Capability |
|---:|---|---|
| 0 | `801cb6d918d0e383e4c6a3c6017ef945d42a0698` | equal-hint short asymmetric-spine optimization |
| 1 | `2de1895a52d21ad266b77002defe3e6bc69bbcfd` | reject underived/orphan recursors |
| 2 | `91ba5db4029290b257a08494559ec3283cddbee3` | wide framed environments for exact deep read sets |
| 3 | `eaf479a135c02e0daad6760eff9e049dd9f63576` | exact wide-read/projected-environment caches |
| 4 | `5daa4f66c1fa63b44d2dd02e96bd7303e6ec0f71` | exact environment keys past 64 loose variables |
| 5 | `d6a73279e6765e637f9741180cefbd7ef957d8e5` | bottom-up wide read-set memoization + one-pass projection |

A mask bit means **retain** that capability.

All 64 masks are frozen before results.

## GENESIS construction

For each mask:

1. checkout the genesis base `16ccc0ed...`;
2. apply selected capability commits in chronological bit order using their exact patches;
3. classify patch conflicts as `UNREACHABLE_PATCH`;
4. otherwise run the protected semantic gate.

No result may add a capability outside this frozen list.

## SOLVENT construction

For the same mask:

1. checkout the full present `d6a73279...`;
2. revert every unselected capability in reverse chronological bit order;
3. classify patch conflicts as `UNREACHABLE_PATCH`;
4. otherwise run the same protected semantic gate.

## Protected semantic gate

A reachable candidate is semantically lawful in this bounded test only if all of the following pass unchanged:

- `cargo test --release --locked`;
- pinned Arena `init-prelude` accepts;
- pinned Arena `extra-rec` rejects;
- pinned Arena `rec-missing-ih` rejects;
- pinned Arena `proj-of-stuck-prop` rejects;
- pinned Arena `proj-of-subst-prop` rejects.

This is a **bounded semantic-sufficiency test**, not a complete Arena promotion test.

## Convergence criterion

For each direction, let the semantic commitment cost be the number of retained capability atoms.

Let:

[
F_G = \operatorname{argmin}_{m:\,G(m)\ lawful} |m|
]

and

[
F_S = \operatorname{argmin}_{m:\,S(m)\ lawful} |m|.
]

Bidirectional convergence passes iff:

1. both frontiers are nonempty;
2. `F_G == F_S` as mask sets;
3. for every mask in the common frontier, the normalized executable source payload (`Cargo.toml`, `Cargo.lock`, `src/`, `tests/`) has the same SHA-256 in both directions.

The test also records all masks that are lawful in only one direction, exposing path dependence in the continuation language.

## Secondary controls

- Every one-bit/single-capability statement is interpreted contextually, not globally.
- No performance claim is derived from retained capability count.
- Hosted timing is not used to claim an Arena ranking improvement.
- If the semantic frontiers converge, the result establishes only a bounded invariant under this six-atom continuation class and protected replay.
- If they do not converge, that is a scientific result: reachability/path dependence prevented the two directions from identifying the same invariant.

## Claim boundary

A pass means:

> Within this frozen six-capability MathGraph continuation class and the protected semantic replay above, genesis and solvent independently identify the same minimum-cardinality semantically sufficient configuration frontier.

It does **not** establish:
- global minimality of the Lean checker;
- optimal Arena performance;
- completeness outside the tested protected replay;
- inevitable genesis/solvent convergence in arbitrary domains.
