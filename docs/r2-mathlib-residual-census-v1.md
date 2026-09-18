# R2 Mathlib Residual Census V1

## Status

Evidence-only experiment. No Arena PR. No R2/R3 capability is promoted by this branch.

## Protected starting point

Qualified R1 commit:

`d3b97093175eee5573caaa00993bac358d00a1dc`

Qualification evidence:

- 409 current Arena exports;
- zero semantic mismatches;
- `R1_FULL_ARENA_SEMANTIC_PARITY_PASS`;
- `R1_FULL_QUALIFICATION_PASS`;
- beta-ladder 19.5x faster than exact R1 ablation;
- no protected workload regression beyond the qualification threshold.

R1 is treated as earned capability and is not modified in this experiment.

## Question

R1 is essentially neutral on full Mathlib, so beta pressure is not sufficient to explain the remaining Mathlib gap.

The census asks which declared next representation portfolio has the stronger structural residual:

- **R2 — environment pressure:** retained environment state is substantially larger than the consequentially live state selected by `key_env`;
- **R3 — conversion/forcing pressure:** conversion repeatedly enters cold work and/or forcing repeatedly performs nontrivial reduction despite existing retained memoization.

The experiment does not assume either answer.

## Consequence contract

Protected semantic consequence:

- exact checker exit status and stdout parity with qualified R1 on every census workload.

Census workload panel:

- `mathlib`;
- `perf/grind-ring-5`;
- `cslib`;
- `cedar`;
- `init`;
- `perf/beta-ladder`;
- `perf/magma-list-deep-n36`;
- `perf/magma-list-pair-n21`.

The panel is deliberately mixed so raw workload size is not mistaken for a Mathlib-specific residual.

## Measurements

The profiling build records only structural counters.

### Environment / R2 evidence

- number of `key_env` calls;
- total environment length before consequential pruning;
- total environment length after pruning;
- fraction of calls that reduce the environment;
- fraction reducing to at most one-half;
- fraction reducing to at most one-quarter;
- wide-environment calls;
- closure applications and inference-closure applications.

### Conversion / forcing / R3 evidence

- top-level conversion calls;
- cacheable conversion states;
- positive union-find hits;
- negative conversion-cache hits;
- probe-negative hits;
- cold conversion entries;
- `force_all` calls;
- retained WHNF-store hits;
- nonzero reductions;
- total reduction steps;
- calls requiring at least 4 or at least 16 steps.

### Existing cache context

- inference cache hits/misses;
- closed-evaluation cache hits/misses;
- open-evaluation cache hits/misses.

## Epistemic rule

This run may output one of:

- `NEXT_PORTFOLIO=R2_ENVIRONMENT_PRESSURE`;
- `NEXT_PORTFOLIO=R3_CONVERSION_FORCE_PRESSURE`;
- `NEXT_PORTFOLIO=UNKNOWN_CHOICE`.

That output is a routing signal only.

It is **not** a performance claim and **not** promotion evidence.

The selected portfolio must then be implemented as the smallest isolated structural intervention, checked against an exact ablation, full semantic parity, protected workload regression gates, and ultimately the official-style Mathlib head-to-head.

## QCKN interpretation

The experiment follows:

```text
qualified R1 present
→ observe Mathlib residual
→ measure structural consequence field
→ classify R2/R3 pressure
→ choose one isolated repair portfolio
→ verify
→ only then consider promotion
```

The profiler is discovery state, not active cognition. It must not ship in the promoted kernel.
