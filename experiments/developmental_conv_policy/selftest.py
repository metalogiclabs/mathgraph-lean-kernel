#!/usr/bin/env python3
from pathlib import Path
import json
import tempfile

from policy_compiler import compile_policy, score


def rec(state, costs):
    actions = {}
    for action, (correct, cost) in costs.items():
        actions[action] = {"correct": correct, "cost": cost}
    return {"state": state, "actions": actions}


def main():
    records = [
        rec({"left_shorter": True, "one_spine_is_one": True, "left_unfoldable": True}, {
            "compare_args": (True, 30), "unfold_left": (True, 3), "unfold_right": (True, 20), "unfold_both": (True, 25), "structural": (True, 40)}),
        rec({"left_shorter": True, "one_spine_is_one": True, "left_unfoldable": True}, {
            "compare_args": (True, 28), "unfold_left": (True, 4), "unfold_right": (True, 18), "unfold_both": (True, 21), "structural": (True, 35)}),
        rec({"right_shorter": True, "one_spine_is_one": True, "right_unfoldable": True}, {
            "compare_args": (True, 27), "unfold_left": (True, 18), "unfold_right": (True, 3), "unfold_both": (True, 20), "structural": (True, 36)}),
        rec({"right_shorter": True, "one_spine_is_one": True, "right_unfoldable": True}, {
            "compare_args": (True, 25), "unfold_left": (True, 17), "unfold_right": (True, 4), "unfold_both": (True, 19), "structural": (True, 34)}),
        rec({"heads_match": True, "shared_subproblem": True}, {
            "compare_args": (True, 2), "unfold_left": (True, 14), "unfold_right": (True, 14), "unfold_both": (True, 18), "structural": (True, 6)}),
        rec({"heads_match": True, "proof_valued": True}, {
            "compare_args": (True, 2), "unfold_left": (True, 16), "unfold_right": (True, 16), "unfold_both": (True, 20), "structural": (True, 5)}),
    ]
    p, s = compile_policy(records, max_clauses=2)
    assert s.semantic_errors == 0
    # It must discover a nontrivial policy; a single global action is deliberately suboptimal.
    assert len(p.clauses) >= 1
    baseline = min(score(type(p)(a), records).total_cost for a in ("compare_args", "unfold_left", "unfold_right", "unfold_both", "structural"))
    assert s.total_cost < baseline, (s.total_cost, baseline, p)
    print("DEVELOPMENTAL_CONV_POLICY_SELFTEST=PASS")
    print(p)
    print(s)


if __name__ == "__main__":
    main()
