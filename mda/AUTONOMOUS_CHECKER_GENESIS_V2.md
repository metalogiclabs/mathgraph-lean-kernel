# Autonomous Checker Mechanism Genesis V2 — Frozen Protocol

**Status:** FROZEN BEFORE V2 CENSUS / POLICY SEARCH / HELD-OUT RESULTS  
**Date:** 2026-09-14

## Provenance

V1 is frozen at `1fc7f1aea30a8f5de7541bfa4d718d9002bed4d4` and ended:

```text
UNKNOWN_NO_TRAINING_WIN
```

under the observation language:

```text
root kind × FV-mask bucket × evaluation-depth bucket
```

No V1 candidate reached the semantic or held-out gates.

The exact residual is therefore:

> the current local observation quotient mixes cache-beneficial and cache-costly events too coarsely to earn a >=1% mechanism change.

V2 makes the smallest generic observation-language expansion below. It does **not** lower the economic threshold or import a historical hand-written selector.

## Starting present

- real checker source: `c6d445a954def8922490d0cd874ea134b45463dd`
- pinned Lean Kernel Arena: `ac1c13762de41b594fa24b90ede8cfd97ac6a765`
- V1 training/held-out split is retained unchanged.

## V2 observation language

Retain all V1 features:

- current root kind: App / Proj / Let / Pi / Lambda
- free-variable-mask population bucket: 0, 1–4, 5–8, 9–16, 17–32, 33–64
- evaluation-depth bucket: 0, 1–2, 3–7, 8+

Add exactly one generic structural refinement:

> **the root kinds of all immediate expression children, in stable AST order, padded to three slots.**

Child-root alphabet:

```text
Var, Sort, Const, App, Pi, Lambda, Let, Proj, NatLit, StringLit, NONE
```

Stable child slots:

- App: (fun, arg, NONE)
- Proj: (structure, NONE, NONE)
- Pi: (binder_type, body, NONE)
- Lambda: (binder_type, body, NONE)
- Let: (binder_type, val, body)

No recursive/grandchild feature, caller feature, workload name, source location, theorem name, or historical branch label is available.

This is a one-step development of the observation language only.

## Finite cell universe

The full V2 key is:

```text
V1 cell × child-root-1 × child-root-2 × child-root-3
```

for at most:

```text
120 × 11^3 = 159,720
```

finite cells.

Instrumentation may census all cells, but mechanism synthesis uses training observations only.

## Unseen-cell rule

A feature key not observed in training inherits the starting present:

```text
UNSEEN -> ADMIT CACHE
```

Therefore V2 can only bypass cells for which the training evidence explicitly earned a change.

## Frozen policy meta-language

Exactly the same threshold family as V1:

- minimum observed hit count `h in {1,2,4,8,16}`
- minimum observed hit ratio `r in {0, 0.01, 0.05, 0.10, 0.20, 0.40}`

For an observed V2 cell:

```text
ADMIT iff hits >= h AND hits/(hits+misses) >= r
otherwise BYPASS
```

Unobserved cells admit by the rule above.

All 30 threshold laws are generated. Behaviorally identical policies may be deduplicated before timing, but the full frozen threshold set must be recorded.

BASE = unchanged accepted present.

ALL_BYPASS = negative control only and is never eligible for promotion.

No policy may be added after results.

## Training and selection

Training workloads remain:

- con-leche
- perf/app-lam
- perf/beta-ladder
- perf/let-ladder

For every distinct policy:

1. semantic success on every training workload is mandatory;
2. one warm-up per workload;
3. two scored wall-time repetitions per workload;
4. primary score = sum of workload medians;
5. no training workload may regress by >10% versus BASE;
6. selected eligible policy minimizes primary score;
7. synthesized policy must beat BASE aggregate by >=1.0%.

Otherwise:

```text
UNKNOWN_NO_TRAINING_WIN_V2
```

and no semantic/held-out promotion occurs.

## Semantic promotion authority

A selected policy is frozen and materialized as Rust before held-out timing.

It must pass:

- `cargo test --release --locked`
- full pinned Lean Kernel Arena build
- full pinned Arena run
- zero incorrect / declined / error semantic rows relative to the accepted starting present.

Performance cannot override semantic failure.

## Held-out promotion

Held-outs remain unopened until semantic authorization:

- mathlib
- perf/grind-ring-5
- perf/shift-cascade

Three scored repetitions each for BASE and CANDIDATE.

Promotion requires:

- aggregate median-sum improvement >=1.0%;
- improvement on at least 2/3 workloads;
- no workload regression >5%.

## Causal ablation

The exact accepted starting source `c6d445...` is the ablation control.

A successful result must show that restoring that source removes the generated V2 admission mechanism and removes/materially shrinks the measured held-out advantage.

## Claim boundary

A pass establishes only:

> Residual-driven development of a one-hop structural observation language enabled a frozen finite mechanism synthesizer to generate a real checker cache-admission policy that preserved pinned Lean semantics and improved unseen workloads.

It does not establish unrestricted checker architecture invention.

## Falsifiers

V2 does not promote if:

- the one-hop observation language yields no >=1% eligible training win;
- a selected policy depends on held-out data;
- training or pinned Arena semantics fail;
- held-out promotion fails;
- the advantage survives exact ablation inconsistently;
- a post-result feature/policy is added.
