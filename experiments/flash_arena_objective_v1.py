#!/usr/bin/env python3
import json, sys
from pathlib import Path

SCHEMA="mathgraph.flash.arena-objective.v1"

def rank_key(x):
    # Mirrors the Arena's lexicographic ordering for tied participants:
    # 1) wrong accepts, 2) wrong rejects, 3) Mathlib instruction count, 4) declines.
    return (
        int(x.get("wrong_accepts",0)),
        int(x.get("wrong_rejects",0)),
        int(x["mathlib_instructions"]),
        int(x.get("declines",0)),
    )

def arena_better(candidate, incumbent):
    return rank_key(candidate) < rank_key(incumbent)

def performance_admission(candidate, incumbent, *, min_mathlib_gain=0.002, catastrophic_secondary_floor=0.90):
    # Semantics/correctness are absolute. A candidate with a new wrong answer is dead,
    # regardless of speed.
    if int(candidate.get("wrong_accepts",0)) > int(incumbent.get("wrong_accepts",0)):
        return False, "wrong_accept_regression"
    if int(candidate.get("wrong_rejects",0)) > int(incumbent.get("wrong_rejects",0)):
        return False, "wrong_reject_regression"

    # If correctness remains tied, Mathlib is the actual ranking objective.
    base=float(incumbent["mathlib_instructions"])
    cand=float(candidate["mathlib_instructions"])
    speedup=base/cand
    if speedup < 1.0 + min_mathlib_gain:
        return False, "mathlib_gain_below_threshold"

    # Secondary workloads are not ranking vetoes, but catastrophic regressions are
    # operational hazards because they can hit timeout/resource constraints.
    for name,ratio in candidate.get("secondary_speedups",{}).items():
        if float(ratio) < catastrophic_secondary_floor:
            return False, f"catastrophic_secondary_regression:{name}"

    return True, "arena_objective_pass"

def main():
    if len(sys.argv)!=3:
        raise SystemExit("usage: flash_arena_objective_v1.py incumbent.json candidate.json")
    inc=json.loads(Path(sys.argv[1]).read_text())
    cand=json.loads(Path(sys.argv[2]).read_text())
    ok,reason=performance_admission(cand,inc)
    print("FLASH_ARENA_OBJECTIVE_V1")
    print("INCUMBENT_RANK_KEY="+repr(rank_key(inc)))
    print("CANDIDATE_RANK_KEY="+repr(rank_key(cand)))
    print("ARENA_BETTER="+str(arena_better(cand,inc)).lower())
    print("ADMISSION="+str(ok).lower())
    print("REASON="+reason)
    raise SystemExit(0 if ok else 1)

if __name__=="__main__":
    main()
