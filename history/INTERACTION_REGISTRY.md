# Contextual Necessity / Interaction Registry

This file records historical evidence imported into the MDA MathGraph domain pack. These observations are **not** global labels such as “necessary” or “redundant”; they are scoped to the tested configuration, workload, build and experimental budget.

## Starting present

`d6a73279e6765e637f9741180cefbd7ef957d8e5`

## V113 — no-wide causal ablation

- Existing wide projection was removed for `k > 64`.
- Hosted-runner wall time improved materially on Mathlib and collapsed on con-leche.
- Retired instruction count was unavailable.
- **Warranted use:** establishes a strong workload-dependent interaction in wall/resource behavior.
- **Not established:** an Arena-ranked improvement, because Arena ranks Mathlib performance by retired instructions rather than hosted wall time.

## V117 — boundary atlas

Run: `34781716973`

- Construction-time features such as depth/app-spine/var-mass explained substantial local variance in immediate projection consequences.
- Universal metadata did not earn promotion as an implementation.
- **Warranted use:** proposal-generation/provenance.
- **Not established:** that local saved/selected yield is a sufficient global retention criterion.

## V118–V119 — selector falsification

- Selectors based on local structural-yield proxies produced severe con-leche resource/runtime growth under the experiment budget.
- Restoring the full V117 conditional coordinates did not cure the problem.
- **Warranted use:** falsifies the local-yield proxy as a sufficient global contraction rule in those experiments.
- **Not established:** that every candidate exceeding the experiment timeout is illegal under Arena scoring.

## V120 — single-group contextual ablations

Run: `34790844462`

Eight deterministic groups of low-local-yield cells were each removed separately. All eight individual candidates completed con-leche in the tested environment; removing the full candidate family produced severe resource/runtime growth and runner termination.

Interpretation:

```text
Redundant(G_i | starting configuration, tested con-leche budget) for each tested i
does not imply
Redundant(union_i G_i | starting configuration, tested con-leche budget)
```

This is evidence for contextual necessity / substitution / complementarity.

## V121 — interaction map

Run: `34792979872`

Observed under the same experimental style:

- mask 15 = groups {0,1,2,3}: severe runtime/resource growth / runner termination;
- mask 85 = groups {0,2,4,6}: severe runtime/resource growth / runner termination;
- masks 240, 170, 51, 204 and tested adjacent pairs completed.

**Correct claim boundary:** interaction is non-additive. These are not yet minimal sufficient sets under the official Arena developmental preorder.

## Process correction

The historical V122 pair/triple sweep is exploratory only. It was selected after inspecting V121 and therefore is not used as an independently frozen promotion test.

The next retained MDA development must begin from the frozen domain contract and baseline, then search lawful configurations under the actual Arena score ordering.
