#!/usr/bin/env python3
import importlib.util,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("fp",ROOT/"experiments/flash_plan_v1.py")
fp=importlib.util.module_from_spec(spec); spec.loader.exec_module(fp)
reg=json.loads((ROOT/"experiments/flash_action_registry_v1.json").read_text())

x=fp.plan({"selected_action":"revalidate_ordinary_unfold_neutral"},reg)
assert x["status"]=="ready"
assert x["type"]=="generation_gate"
assert x["capability_id"]=="ordinary_unfold_neutral"

y=fp.plan({"selected_action":"rigid_inductive_exact_interface_census"},reg)
assert y["status"]=="ready"
assert y["authority"]=="observational_only"

z=fp.plan({"selected_action":"revalidate_rigid_inductive_v2"},reg)
assert z["status"]=="ready"
assert z["type"]=="generation_gate"
assert z["capability_id"]=="rigid_inductive_neutral_v2"

try:
    fp.plan({"selected_action":"invent_something_unregistered"},reg)
except ValueError as e:
    assert "unregistered" in str(e)
else:
    raise AssertionError("unregistered action was accepted")

print("FLASH_ACTION_PLAN_TESTS_PASS")
