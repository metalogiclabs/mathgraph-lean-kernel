#!/usr/bin/env python3
import importlib.util, json
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("flash_controller", ROOT/"experiments/flash_controller_v1.py")
fc=importlib.util.module_from_spec(spec); spec.loader.exec_module(fc)

evidence=json.loads((ROOT/"experiments/flash_closure_v1_evidence.json").read_text())
manifest=json.loads((ROOT/"experiments/flash_capability_manifest_v1.json").read_text())

base=fc.close(deepcopy(evidence),deepcopy(manifest))
assert base["runtime_policy"]["promoted"]==["direct_var_eval"]
assert base["selected_action"]=="revalidate_direct_framed_prune"

passed=deepcopy(evidence)
passed["events"].append({
    "id":"test-framed-pass","kind":"current_revalidation","capability_id":"direct_framed_prune",
    "run":1,"semantic_pass":True,"performance_pass":True,
})
p=fc.close(passed,deepcopy(manifest))
assert p["runtime_policy"]["promoted"]==["direct_framed_prune","direct_var_eval"]
assert p["selected_action"]=="app_simple_apply_new_representation"

failed=deepcopy(evidence)
failed["events"].append({
    "id":"test-framed-fail","kind":"current_revalidation","capability_id":"direct_framed_prune",
    "run":2,"semantic_pass":True,"performance_pass":False,
})
f=fc.close(failed,deepcopy(manifest))
assert f["runtime_policy"]["promoted"]==["direct_var_eval"]
assert next(c for c in f["manifest"]["capabilities"] if c["id"]=="direct_framed_prune")["status"]=="rejected"

# Dependency revocation: promote framed, then reject its required direct-Var dependency.
rev=deepcopy(evidence)
rev["events"] += [
    {"id":"test-framed-pass2","kind":"current_revalidation","capability_id":"direct_framed_prune",
     "run":3,"semantic_pass":True,"performance_pass":True},
    {"id":"test-var-fail","kind":"current_revalidation","capability_id":"direct_var_eval",
     "run":4,"semantic_pass":False,"performance_pass":False},
]
rv=fc.close(rev,deepcopy(manifest))
statuses={c["id"]:c["status"] for c in rv["manifest"]["capabilities"]}
assert statuses["direct_var_eval"]=="rejected"
assert statuses["direct_framed_prune"]=="revoked"
assert "direct_var_eval" not in rv["runtime_policy"]["promoted"]
assert "direct_framed_prune" not in rv["runtime_policy"]["promoted"]

print("FLASH_CONTROLLER_TRANSITION_TESTS_PASS")
