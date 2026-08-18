# Infer beta-fusion phase-change experiment

Frozen baseline: V1 commit `1e209dad266d59b4d43cdea189876bc6ea551339`.

## Evidence entering this test

* beta-2000: `infer.rs:170` emits ~2,000,000 `force_all` calls; 99.9985% are already `Pi`.
* beta-8000: the same site emits ~32,000,000 calls; 99.9999% are already `Pi`.
* 4x ladder depth therefore gives 16x demand at one site.
* A local Pi fast return gives ~10% wall gain, but does not change the quadratic demand curve.

## Causal hypothesis

The `force_all` flood is a symptom of a larger duplicated derivation. `infer_app_v` first infers a lambda as a Pi, which in Check mode recursively checks the lambda body; applying that Pi then causes the same nested application/lambda suffix to be inferred again under the instantiated environment. On beta-ladder this repeats suffixes and generates the triangular / quadratic work.

For a direct beta redex `(fun x : A => body) arg`, use the typing rule directly: check `A` is a sort, check `arg : A`, then infer/check `body` once under the environment extended by the actual argument and context extended by `A`. This fuses lambda inference with application inference instead of materializing a Pi only to consume it immediately.

## Arms

1. exact V1 baseline;
2. proven inner Pi-WHNF fast path;
3. direct infer-beta fusion;
4. fusion + Pi-WHNF fast path.

## Fast deciding measurements

* semantic output equality on beta-2000 and beta-8000;
* 5 wall repetitions on beta-2000, beta-4000, beta-8000;
* instrument `infer.rs:170` call count in fusion arm to see whether the n^2 source collapses;
* protected sniff tests: app-lam, let-ladder, grind-ring-5.

## Promotion criterion

Phase-change success requires both:

1. semantic equality on all tested workloads; and
2. beta scaling bends materially away from the V1 quadratic curve (target >=2x speedup at beta-8000 or >=50% reduction in the dominant infer/force demand).

If the fast gate succeeds, immediately run the Arena test suite / leaderboard-oriented full validation before any upstream PR is created. If semantics fail, reject this formulation and use the counterexample to repair the fused typing rule rather than weakening the gate.
