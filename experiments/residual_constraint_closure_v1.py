#!/usr/bin/env python3
"""Retrospective test of residual multi-typing / constraint-closure claims.

This is deliberately small and auditable.  It does NOT train on numerical
outcomes.  Each trial records:
  * a law/constraint that was available before the target intervention,
  * the target intervention family,
  * the prediction implied by the prior constraint,
  * the later verifier/performance outcome.

The aim is to test whether constraints learned in one residual cluster transfer
to later, differently-shaped residuals.  It is retrospective evidence, not an
independent prospective validation; the final trial is left prospective.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Trial:
    name: str
    source_prs: tuple[int, ...]
    target_pr: int | None
    prior_constraint: str
    candidate: str
    prediction: str
    observed: str
    pass_expected: bool | None
    transfer: str


TRIALS = [
    Trial(
        name="quotient size does not imply removable work -> conversion scheduler",
        source_prs=(10, 11),
        target_pr=32,
        prior_constraint=(
            "A large behavioral quotient/event population is insufficient evidence of "
            "computational reuse unless the recognition/intervention cost is cheaper than "
            "the work removed."
        ),
        candidate="equal-hint one-side / shorter-spine scheduling",
        prediction="Do not predict a material gain from the ~2M choice population alone.",
        observed=(
            "Corrected full-Mathlib rerun rejected all three arms: left +1.10%, "
            "right +1.42%, shorter +3.42% wall time."
        ),
        pass_expected=True,
        transfer="iota -> conversion",
    ),
    Trial(
        name="quotient size does not imply removable work -> structural pre-key",
        source_prs=(10, 11, 32),
        target_pr=43,
        prior_constraint=(
            "Repeated/regular events are not a speedup opportunity unless semantic "
            "equivalence can be recognized more cheaply than executing the original path."
        ),
        candidate="exact structural projected-environment pre-key",
        prediction=(
            "Treat 165M cold-hit materializations as opportunity evidence only; penalize a "
            "candidate that separately recomputes essentially the same semantic projection."
        ),
        observed=(
            "Semantics held, but init/std instructions regressed +23.8% to +27.0% and "
            "Mathlib wall regressed +31.7% to +35.4%."
        ),
        pass_expected=True,
        transfer="iota + conversion -> environment representation",
    ),
    Trial(
        name="semantic quotient identity dominates provenance identity",
        source_prs=(16, 17, 18, 29, 30, 40, 41),
        target_pr=42,
        prior_constraint=(
            "Open-cache identity is the canonical projected semantic environment; source "
            "environment provenance is not established as an equivalent quotient."
        ),
        candidate="source-environment pointer pre-prune cache",
        prediction="Reject as semantically unsafe until equivalence to canonical projection is proved.",
        observed="The intervention failed the real init semantic gate with `expected a pi type`.",
        pass_expected=True,
        transfer="environment identity -> cache design",
    ),
    Trial(
        name="capacity residual predicts structural rather than larger-cache intervention",
        source_prs=(28, 29),
        target_pr=30,
        prior_constraint=(
            "1K/16K/64K/256K prune-cache arms are capacity-flat; remaining cold projections "
            "should be treated as structural rather than cache-capacity misses."
        ),
        candidate="another larger prune cache",
        prediction="Eliminate the capacity-tuning family and move to identity/representation tests.",
        observed="The programme moved to carried canonical identity and later representation-level censuses.",
        pass_expected=True,
        transfer="capacity -> representation",
    ),
    Trial(
        name="probe economics blocks a global lower-budget policy",
        source_prs=(36,),
        target_pr=None,
        prior_constraint=(
            "96.08% of probe passes succeed and failed probes consume only 4.06% of probe work; "
            "a rare ~2000-work success is strategically required."
        ),
        candidate="lower the global spine-probe budget",
        prediction="Eliminate the global-budget family despite the discarded-argument failure case.",
        observed="No later evidence justifies reopening the global-budget family; profiling moved elsewhere.",
        pass_expected=True,
        transfer="microbenchmark routing -> workload policy",
    ),
    Trial(
        name="current prospective representation-gap prediction",
        source_prs=(29, 39, 40, 41, 42, 43),
        target_pr=None,
        prior_constraint=(
            "The remaining environment object must preserve canonical semantic identity and cache reuse, "
            "must not depend on larger cache capacity, and must not compute a separate full structural key. "
            "Cold projections are predominantly tiny and shallow."
        ),
        candidate="intrinsically canonical tiny (0/1/2-slot) projected closure representation",
        prediction=(
            "This family has the highest current constraint coverage; test it against exact V2 with "
            "soundness first, deterministic instructions second, and full Mathlib transfer."
        ),
        observed="PROSPECTIVE — not yet tested.",
        pass_expected=None,
        transfer="constraint closure -> operator type signature",
    ),
]


def main() -> None:
    historical = [t for t in TRIALS if t.pass_expected is not None]
    passed = sum(bool(t.pass_expected) for t in historical)
    print("RESIDUAL CONSTRAINT-CLOSURE RETROSPECTIVE V1")
    print(f"historical_trials={len(historical)}")
    print(f"directionally_consistent={passed}/{len(historical)}")
    print("NOTE=manual evidence typing; retrospective; not an independent proof")
    print()
    for i, t in enumerate(TRIALS, 1):
        status = "PROSPECTIVE" if t.pass_expected is None else ("PASS" if t.pass_expected else "FAIL")
        print(f"T{i}: {status} :: {t.name}")
        print(f"  source_prs={','.join('#'+str(x) for x in t.source_prs)}")
        print(f"  target_pr={'#'+str(t.target_pr) if t.target_pr else '-'}")
        print(f"  transfer={t.transfer}")
        print(f"  constraint={t.prior_constraint}")
        print(f"  candidate={t.candidate}")
        print(f"  prediction={t.prediction}")
        print(f"  observed={t.observed}")
        print()

    print("FALSIFICATION CONDITIONS")
    print("  1. A future candidate violating a hard verified invariant wins while the invariant remains valid.")
    print("  2. A count/quotient-only candidate repeatedly yields material real-workload gains despite high recognition cost.")
    print("  3. Constraint-closure ranking does not beat simpler hotspot/event-count baselines on prospective episodes.")
    print("  4. The prospective tiny-canonical family is not privileged: if it fails, record the failure as a new type constraint.")


if __name__ == "__main__":
    main()
