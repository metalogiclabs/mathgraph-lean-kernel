# MDA Blind Residual Localization V4a — Results

**Verdict:** `VERIFIED_BLIND_COMPUTATIONAL_RESIDUAL_LOCALIZATION`

- Run: `34813702094`
- Workflow head: `6d720dc782c9c575953cb5718f60f8b87937fa00`
- Artifact: `10335178160`
- Artifact SHA-256: `4205fccf4da08e54622f137d1c3b75bebb0c4ff4220a1834069e2f4214ae7312`

## Result

Starting only from the SEED/FRONTIER behavioral contrast on `con-leche`, task-clock profiling localized a strong residual without using the historical optimization narrative.

Seven symbols met the frozen localization threshold.

Top residuals:

| # | symbol | SEED % | FRONTIER % | residual pp |
|---:|---|---:|---:|---:|
| 1 | `TypeChecker::eval_no_cache` | 10.30 | 4.26 | **+6.04** |
| 2 | `TypeChecker::eval` | 14.76 | 9.81 | **+4.95** |
| 3 | `TypeChecker::infer_value` | 10.97 | 8.10 | **+2.87** |
| 4 | `TypeChecker::mk_unfold_hc` | 4.75 | 3.44 | **+1.31** |
| 5 | value-cache hash table rehash | 1.29 | 0.00 | **+1.29** |

The top five positive residuals account for **16.46 percentage points** of exclusive sampled task-clock share. Top ten account for **18.69 pp**.

The largest single signal is `eval_no_cache`, whose sampled share is about **2.42x** the FRONTIER share.

## Interpretation

The forcing workload does not initially point to a named historical capability. It points to a generic computational fact:

> the minimum semantic present is spending disproportionate work in uncached/repeated evaluation, with additional pressure in inference and value-cache allocation.

This is enough to justify a new diagnostic step directed at evaluation/cache pressure without importing the historical wide-environment solution.

## Claim boundary

This is localization, not causal proof. Task-clock share identifies where the SEED spends relatively more work; it does not yet prove which representation or cache repair should be retained.
