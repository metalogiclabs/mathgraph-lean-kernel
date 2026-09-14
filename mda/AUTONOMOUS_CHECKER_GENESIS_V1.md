# Autonomous Checker Mechanism Genesis V1 — Frozen Protocol

**Status:** FROZEN BEFORE INSTRUMENTATION / SEARCH / HELD-OUT RESULTS  
**Date:** 2026-09-14

## Starting present

- Repository: `metalogiclabs/mathgraph-lean-kernel`
- Starting checker commit: `c6d445a954def8922490d0cd874ea134b45463dd`
- Starting mechanism: accepted warm-projection candidate
- Lean Kernel Arena: `ac1c13762de41b594fa24b90ede8cfd97ac6a765`

The starting present already passed the full pinned Arena semantic replay and improved local Mathlib/con-leche wall time relative to the prior present.

## Scientific question

Can a frozen generic developmental mechanism use a real checker residual to:

1. measure which local evaluation contexts actually benefit from an existing memoizing path;
2. synthesize a new executable cache-admission mechanism not present in the starting checker;
3. select it using training workloads only;
4. integrate it into the real Rust checker;
5. preserve the full pinned Arena semantic gate;
6. improve frozen held-out performance;
7. lose that performance benefit under exact ablation back to the starting present?

A pass is a bounded instance of:

> verified intelligence changing its own mediation of consequence in a real theorem checker.

It is **not** unrestricted mechanism invention. The mechanism is synthesized inside the frozen policy meta-language below.

---

## Frozen residual provenance

Independent prior profiling localized a real computational residual to repeated uncached evaluation around `TypeChecker::eval_no_cache`, including a qualified nested/re-entrant caller path.

Earlier independent feature-atlas work also showed that coarse local expression features can mix useful and pathological evaluation cases.

Those results motivate where to observe; they do **not** supply the final policy.

No historical hand-written cache selector is imported.

---

## Frozen meta-language

The current checker's open-expression evaluation path contains a memoizing mechanism over expression/environment keys.

The only candidate changes allowed in V1 are **contextual admission policies** deciding whether this existing memoizing path is used for a local evaluation context.

The policy language contains no named workload, theorem, source location, historical branch, or manually chosen special case.

### Observable local features

For each open-expression evaluation event:

- expression root kind among: App, Proj, Let, Pi, Lambda;
- free-variable-mask population bucket:
  - 0
  - 1–4
  - 5–8
  - 9–16
  - 17–32
  - 33–64
- evaluation-depth bucket:
  - 0
  - 1–2
  - 3–7
  - 8+

This gives 120 finite local cells.

### Observation phase

On the frozen training workloads, instrumentation records for every cell:

- cache hits;
- cache misses.

No held-out workload is inspected during policy synthesis.

### Policy synthesis

Candidate policies are generated mechanically from the observed training table.

For each frozen pair of thresholds:

- minimum observed hit count `h in {1,2,4,8,16}`;
- minimum observed hit ratio `r in {0, 0.01, 0.05, 0.10, 0.20, 0.40}`;

a cell admits memoization iff:

```text
hits >= h
AND
hits / (hits + misses) >= r
```

The unchanged starting policy “admit every current open-expression cell” is included as BASE.

The all-bypass policy is included as a negative control.

No other policy may be added after results are seen.

---

## Frozen workloads

### Training / mechanism construction

Only these workloads may influence policy choice:

- `con-leche`
- `perf/app-lam`
- `perf/beta-ladder`
- `perf/let-ladder`

Selection metric:

1. semantic success on every training workload is mandatory;
2. for each policy, run 2 timing repetitions per workload after one warm-up;
3. primary score = sum of per-workload median wall times;
4. a synthesized policy is eligible only if no training workload regresses by more than 10% versus BASE;
5. select the eligible policy with minimum primary score;
6. if no synthesized policy beats BASE by at least 1.0% aggregate, return `UNKNOWN_NO_TRAINING_WIN` and do not promote.

Threshold/policy complexity is used only as a deterministic tie-break:
fewer admitted cells, then lexicographic threshold order.

### Held-out / promotion

The selected policy is frozen before any held-out timing is opened.

Held-out workloads:

- `mathlib`
- `perf/grind-ring-5`
- `perf/shift-cascade`

For each, run 3 repetitions for BASE and selected candidate under the same build mode.

Promotion performance criterion:

- candidate aggregate sum of medians must improve by at least 1.0%;
- candidate must improve at least 2 of 3 held-out workloads;
- no held-out workload may regress by more than 5%.

If this fails, the scientific result is negative and no candidate branch is promoted.

---

## Semantic authority

Before performance promotion, the selected candidate must pass:

1. `cargo test --release --locked`;
2. full pinned Lean Kernel Arena test build;
3. full pinned Arena checker run;
4. zero rows classified `incorrect`, `declined`, or `error` where the starting accepted present was semantically correct.

Performance may never override semantic failure.

---

## Causal ablation

If a candidate passes held-out promotion:

1. record the generated source policy and its feature table;
2. compare candidate against the exact frozen starting present under the same held-out harness;
3. ablate only the generated admission mechanism by restoring the original “admit all current memoized open-expression cells” logic;
4. require the held-out aggregate advantage to disappear or materially shrink.

The starting present is the ablation control.

---

## Integration / publication

Only if all semantic and held-out gates pass:

- commit the generated `src/eval.rs` mechanism plus machine-readable policy evidence;
- push it to `candidate/autonomous-cache-admission-v1`.

The generated branch must be reconstructible from the frozen starting SHA plus the emitted policy table.

---

## Claim boundary

A pass establishes only:

> Within a frozen finite local-policy meta-language, runtime evidence from real Lean workloads synthesized and integrated a new cache-admission mechanism, preserved pinned verifier semantics, improved held-out workloads, and lost the benefit under ablation.

It does **not** establish unrestricted invention of arbitrary checker architectures, globally optimal cache policy, or universal developmental intelligence.

## Falsifiers

V1 fails to promote if any of the following occurs:

- instrumentation cannot be built without changing checker semantics;
- no synthesized policy beats BASE under the frozen training rule;
- selected policy depends on held-out data;
- full pinned Arena semantics fail;
- held-out promotion gates fail;
- the reported advantage survives exact ablation in a way inconsistent with the generated mechanism;
- generated policy requires workload names or manually added post-result special cases.
