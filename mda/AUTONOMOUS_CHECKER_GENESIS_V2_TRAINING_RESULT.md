# Autonomous Checker Mechanism Genesis V2 — Training Result

**Frozen protocol:** `e5db03ccba629f5dc8b3e2126bc55f000a76065b`  
**Starting checker:** `c6d445a954def8922490d0cd874ea134b45463dd`  
**Training run:** 34832150282  
**Job:** 103937716637  
**Training artifact:** 10343104782

## Verdict

```text
SELECTED_FOR_SEMANTIC_GATE
```

Selected frozen policy:

```text
h4_r0p2
```

## Observation-language expansion

V1's coarse cell language was expanded by one generic structural layer:

```text
root × FV-mask bucket × eval-depth bucket × immediate-child root-shape
```

The V2 census observed:

- 1,006 distinct structural cells;
- 63,639,788 cache hits;
- 73,304,904 cache misses.

All 30 frozen threshold laws produced distinct policy behaviors.

## Selected training mechanism

```text
hits >= 4
AND
hit_ratio >= 0.20
```

for observed cells; unseen cells retain the starting present and admit caching.

The selected policy bypasses 590 of the 1,006 training-observed structural cells.

Frozen training metrics:

- aggregate score: 11.84 s
- aggregate improvement vs BASE: 1.701951017%
- con-leche regression: -1.975945017% (improvement)
- app-lam regression: 0%
- beta-ladder regression: +6.666666667%
- let-ladder regression: 0%

The candidate therefore satisfied the frozen:
- >=1% aggregate training win;
- <=10% per-workload regression ceiling.

## Scientific status

This is not yet a checker promotion.

The selected policy is frozen before any held-out result and is authorized only for:
1. deterministic Rust materialization;
2. full pinned Lean Kernel Arena semantic replay.

Held-out workloads remain unauthorized until the semantic gate is green.
