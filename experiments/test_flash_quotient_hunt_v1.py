#!/usr/bin/env python3
import importlib.util,json
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("hunt",ROOT/"experiments/flash_quotient_hunt_v1.py")
hunt=importlib.util.module_from_spec(spec); spec.loader.exec_module(hunt)
reg=json.loads((ROOT/"experiments/flash_quotient_registry_v1.json").read_text())

plan=hunt.close(reg)
assert plan["selected"]["id"]=="infer.pi.redundant_force_all"
assert plan["selected"]["action"]=="MEASURE_ARENA_PREFERENCE"

unfold=next(x for x in plan["rows"] if x["id"]=="app.ordinary_unfold.generic_apply")
assert unfold["epistemic"]=="DIST_CONTEXT"
assert unfold["action"]=="RETAIN_SEPARATOR"

# UNKNOWN may never be promoted.
prehash=next(x for x in plan["rows"] if x["id"]=="app.canonical_pair.generic_hashing")
assert prehash["epistemic"]=="UNKNOWN"
assert prehash["action"]=="MEASURE_EQUIVALENCE"

# Once Infer-Pi gets rank authority, promotion is the immediate transition.
reg2=deepcopy(reg)
ip=next(x for x in reg2["distinctions"] if x["id"]=="infer.pi.redundant_force_all")
ip["authority"]["preference"]="PASS"
p2=hunt.close(reg2)
assert p2["selected"]["id"]=="infer.pi.redundant_force_all"
assert p2["selected"]["action"]=="PROMOTE_CHEAPEST_REPRESENTATIVE"

# After Infer-Pi is promoted, Rigid V2's missing full congruence is next.
ip["status"]="PROMOTED"
reg2["current_present"].append("infer_pi_demand_bypass")
p3=hunt.close(reg2)
assert p3["selected"]["id"]=="app.rigid_inductive.redundant_function_canonicalization"
assert p3["selected"]["action"]=="MEASURE_RIGHT_CONGRUENCE"

# Once Rigid V2 has full congruence, rank authority becomes its next question.
rv2=next(x for x in reg2["distinctions"] if x["id"]=="app.rigid_inductive.redundant_function_canonicalization")
rv2["authority"]["congruence"]="PASS"
p4=hunt.close(reg2)
assert p4["selected"]["id"]=="app.rigid_inductive.redundant_function_canonicalization"
assert p4["selected"]["action"]=="MEASURE_ARENA_PREFERENCE"

print("FLASH_QUOTIENT_HUNT_TESTS_PASS")
