# MDA SOLVENT Protocol v1 — MathGraph Lean Kernel

**Status:** frozen bounded contraction class, pre-result  
**Starting present:** `d6a73279e6765e637f9741180cefbd7ef957d8e5`  
**Domain contract:** `domains/lean-kernel/DOMAIN_CONTRACT.md`  
**MDA freeze:** `mda/FREEZE.md`

## Purpose

Search inward over configurations of retained capability already present in the frozen starting checker.

This protocol does not ask which historical optimization “looks unnecessary.” It defines a finite continuation class before observing the new solvent results and lets replay/measurement decide which configurations remain lawful.

## Capability atoms

The atoms come directly from the retained-capability registry in `present/PRESENT.json`.

| Bit | Commit | Retained capability |
|---:|---|---|
| 0 | `801cb6d918d0` | equal-hint short asymmetric-spine optimization |
| 1 | `2de1895a52d2` | reject underived/orphan recursors |
| 2 | `91ba5db40292` | wide framed environments for exact deep read sets |
| 3 | `eaf479a135c0` | exact wide-read/projected-environment caches |
| 4 | `5daa4f66c1fa` | exact environment keys past 64 loose variables |
| 5 | `d6a73279e676` | bottom-up wide read-set memoization + one-pass projection |

A mask bit means **contract that retained atom** by reverting its recorded commit.

## Bounded continuation class

For every mask `m in [0,63]`:

1. begin from the exact starting present;
2. revert every selected atom in reverse chronological order;
3. if the patch sequence conflicts, record `UNREACHABLE_PATCH`;
4. if the resulting source does not compile/test, record `UNREACHABLE_BUILD`;
5. otherwise it is a constructible candidate in this bounded `Reach_1(P)`.

No claim of completeness is made outside this six-atom contraction class.

## Stage A — fast protected replay

Every constructible candidate must first pass:

- `cargo test --release --locked`;
- pinned Arena `init-prelude` acceptance;
- pinned adversarial rejects:
  - `extra-rec`;
  - `rec-missing-ih`;
  - `proj-of-stuck-prop`;
  - `proj-of-subst-prop`.

Stage A is a screening gate only. Passing it does not authorize retention.

## Stage B — ranking-relevant replay

Stage-A survivors are subsequently tested unchanged on the pinned Arena ground needed for promotion, including Mathlib.

For each survivor record:

- expected semantic outcome;
- wall/user/sys/RSS measurements;
- authoritative retired instruction count if available.

Con-leche and other stress cases are auxiliary measurements unless explicitly promoted into protected consequence by a prior frozen contract revision.

## Preference

Apply the frozen domain preorder:

1. wrongly accepted invalid proofs;
2. wrongly rejected valid proofs;
3. Mathlib instruction-derived Arena time;
4. declines/crashes;
5. only after official ties, auxiliary engineering measurements.

If authoritative instruction evidence is unavailable, Stage B may identify **promotion candidates**, but must return `UNKNOWN_AUTHORITY` for an Arena performance-win claim.

## Joint sufficiency

The solvent output is a frontier of lawful configurations, not a set of individually indispensable atoms.

A bit may be removable in one candidate and necessary in another. Every result is recorded as contextual evidence relative to its complete mask.

## Historical evidence

V113–V122 may be used only for provenance and interpretation after this search. They do not alter the mask set, success criteria, or stage ordering.

## Freeze rule

After Stage A begins, do not:

- add/remove capability atoms;
- alter expected outcomes;
- edit the mask construction rule;
- change the semantic gate based on observed candidate performance.

Harness-only failures may be repaired if candidate construction and success criteria remain unchanged and the repair is explicitly documented.
