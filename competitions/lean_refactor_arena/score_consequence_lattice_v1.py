#!/usr/bin/env python3
"""Finite, source-bound score-interaction census for Lean proof witness operators.

Checks measurements supplied by already completed pinned Lean runs.
This code never proves a Lean theorem, infers all-version compatibility,
compiles proofs, promotes a candidate, or extrapolates an error bound
to unseen theorem families. It only computes consequences of the finite
measured table and preserves exact negative interaction evidence.
"""
from __future__ import annotations
import argparse
import json
from decimal import Decimal
from pathlib import Path

TYPING_NAME = "Cslib.LambdaCalculus.LocallyNameless.Fsub.Typing.progress"
SKI_NAME = "Cslib.SKI.parallelReduction_diamond"
PIN = "7f3a401470d04f70013d293db4253b088ec8a0ae"
AXES = "TCLR"
MASKS = ("", "T", "C", "L", "R", "TC", "TL", "TR", "CL", "CR",
         "LR", "TCL", "TCR", "TLR", "CLR", "TCLR")


def rows(path: Path) -> dict[str, dict]:
    raw = [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines()
           if s.strip()]
    assert raw, "EMPTY_SCORE_TABLE"
    assert all(isinstance(r, dict) and isinstance(r.get("candidate_label"), str)
               for r in raw), "INVALID_SCORE_ROW"
    result = {r["candidate_label"]: r for r in raw}
    assert len(result) == len(raw), "DUPLICATE_MEASUREMENT_ID"
    return result


def cents(x: object) -> int:
    d = Decimal(str(x)) * 100
    assert d == d.to_integral_value(), "NOT_AN_EXACT_PRINTED_HUNDREDTH"
    return int(d)


def warranted_primary(row: dict, name: str) -> int:
    assert row["name"] == name, "THEOREM_ID_CHANGED"
    assert row.get("compiled") is True and row.get("statement_ok") is True
    assert row.get("eligible") is True and not row.get("forbidden")
    assert not row.get("extra_toplevel_decls") and not row.get("untested")
    assert row.get("compat") == {"v4.33.0-rc2": True}, "WRONG_PINNED_PRIMARY_VERSION"
    versions = row.get("per_version") or []
    assert len(versions) == 1 and versions[0].get("version") == "v4.33.0-rc2"
    assert versions[0].get("tested") is True and versions[0].get("ok") is True
    assert not versions[0].get("errors")
    return cents(row["objective_sum_pct"])


def typing_census(raw: dict[str, dict]) -> dict:
    prefix = "typing_v20_compound_"
    control = "typing_v20_exact_308_control"
    expected = {control} | {prefix + mask for mask in MASKS if mask}
    assert set(raw) == expected and len(raw) == 16, "MISSING_OR_EXTRA_TYPING_CANDIDATE"
    objective = {label: warranted_primary(row, TYPING_NAME)
                 for label, row in raw.items()}
    baseline = objective[control]
    gains = {bit: objective[prefix + bit] - baseline for bit in AXES}
    evidence = []
    for mask in MASKS:
        label = control if mask == "" else prefix + mask
        actual = objective[label]
        predicted = baseline + sum(gains[bit] for bit in mask)
        evidence.append({
            "label": label, "mask": mask or "identity",
            "observed_objective_centipoints": actual,
            "additive_prediction_centipoints": predicted,
            "signed_interaction_centipoints": actual - predicted,
            "positive_vs_control": actual > baseline,
        })
    err = max(abs(x["signed_interaction_centipoints"]) for x in evidence)
    assert baseline == 12003 and objective[prefix + "TCLR"] == 12251
    assert gains == {"T": 98, "C": 75, "L": 37, "R": 37}
    assert err == 2, "TYPING_FINITE_INTERACTION_WARRANT_DRIFT"
    return {
        "source": "pinned primary Lean run 38004209274",
        "measurement_scope": "one theorem, v4.33 primary, 16/16 accepted",
        "baseline_centipoints": baseline,
        "single_operator_gain_centipoints": gains,
        "maximum_observed_abs_interaction_centipoints": err,
        "all_four_actual_centipoints": objective[prefix + "TCLR"],
        "all_four_predicted_centipoints": baseline + sum(gains.values()),
        "measured_composites": evidence,
    }


def ski_census(raw: dict[str, dict]) -> dict:
    requested = ("ski_v18_exact_v13_control", "ski_v18_group_I",
                 "ski_v18_group_S", "ski_v18_group_IS")
    assert all(label in raw for label in requested), "MISSING_SKI_PROBE"
    objectives = {label: warranted_primary(raw[label], SKI_NAME)
                  for label in requested}
    baseline, i, s, is_ = (objectives[label] for label in requested)
    predicted = i + s - baseline
    interaction = is_ - predicted
    assert (baseline, i, s, is_) == (10291, 10106, 10322, 10131)
    assert interaction == -6, "S_K_I_INTERACTION_WARRANT_DRIFT"
    return {
        "source": "pinned primary Lean run 38008324035",
        "measurement_scope": "second theorem, v4.33 primary, four observed comparisons",
        "baseline_centipoints": baseline,
        "I_observed_centipoints": i,
        "S_observed_centipoints": s,
        "IS_observed_centipoints": is_,
        "IS_additive_prediction_centipoints": predicted,
        "IS_signed_interaction_centipoints": interaction,
        "nonmonotone_under_correct_composition": is_ < max(i, s),
    }


def analyze(typing: Path, ski: Path) -> dict:
    tc = typing_census(rows(typing))
    sc = ski_census(rows(ski))
    return {
        "schema": "mathgraph.lra.cost-consequence-lattice.v1",
        "state": "WARRANTED_FINITE_PRIMARY_MEASUREMENTS__NO_GENERALIZATION",
        "source_pin": PIN,
        "exact_source_runs": [38004209274, 38008324035],
        "typing": tc,
        "ski": sc,
        "held_out_interaction_exceeds_typing_envelope": (
            abs(sc["IS_signed_interaction_centipoints"]) >
            tc["maximum_observed_abs_interaction_centipoints"]
        ),
        "safe_reuse": "Prioritize unverified composites by prediction, but never prune or promote without fresh exact Lean and required-version cost checks.",
        "never_claims": [
            "universal score additivity", "valid proof by model prediction",
            "bounded interaction on unseen theorem", "official Arena rank",
            "portfolio mutation", "automatic admission",
        ],
        "officially_submitted": False,
        "portfolio_mutated": False,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--typing", type=Path, required=True)
    p.add_argument("--ski", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    result = analyze(args.typing, args.ski)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    assert result["held_out_interaction_exceeds_typing_envelope"]
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("typing", "ski")}, indent=2))
    print("VERIFIED_FINITE_PRIMARY_COST_INTERACTIONS_WITH_HELDOUT_SEPARATOR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
