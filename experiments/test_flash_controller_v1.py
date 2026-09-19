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
assert base["runtime_policy"]["promoted"]==["direct_framed_prune","direct_var_eval"]
assert next(c for c in base["manifest"]["capabilities"] if c["id"]=="ordinary_unfold_neutral")["status"]=="candidate_reverify"
assert base["selected_action"]=="measure_ordinary_unfold_instructions"

unfold_pass=deepcopy(evidence)
unfold_pass["events"].append({
    "id":"test-unfold-pass","kind":"current_revalidation","capability_id":"ordinary_unfold_neutral",
    "run":5,"semantic_pass":True,"performance_pass":True,"authority_join_verified":True,
})
up=fc.close(unfold_pass,deepcopy(manifest))
assert up["runtime_policy"]["promoted"]==["direct_framed_prune","direct_var_eval","ordinary_unfold_neutral"]
assert up["selected_action"]=="revalidate_rigid_inductive_v2"

rank_reject=deepcopy(evidence)
rank_reject["events"].append({
    "id":"test-unfold-rank-reject","kind":"performance_rejection",
    "capability_id":"ordinary_unfold_neutral","run":6,
    "metric":"mathlib_instructions","performance_rejection_verified":True,
})
ur=fc.close(rank_reject,deepcopy(manifest))
assert next(c for c in ur["manifest"]["capabilities"] if c["id"]=="ordinary_unfold_neutral")["status"]=="rejected"
assert ur["selected_action"]=="revalidate_rigid_inductive_v2"

failed=deepcopy(evidence)
failed["events"].append({
    "id":"test-framed-fail","kind":"current_revalidation","capability_id":"direct_framed_prune",
    "run":2,"semantic_pass":True,"performance_pass":False,"authority_join_verified":True,
})
f=fc.close(failed,deepcopy(manifest))
assert f["runtime_policy"]["promoted"]==["direct_var_eval"]
assert next(c for c in f["manifest"]["capabilities"] if c["id"]=="direct_framed_prune")["status"]=="rejected"

# Dependency revocation: reject direct-Var after Framed has already been promoted.
rev=deepcopy(evidence)
rev["events"].append(
    {"id":"test-var-fail","kind":"current_revalidation","capability_id":"direct_var_eval",
     "run":4,"semantic_pass":False,"performance_pass":False,"authority_join_verified":True}
)
rv=fc.close(rev,deepcopy(manifest))
statuses={c["id"]:c["status"] for c in rv["manifest"]["capabilities"]}
assert statuses["direct_var_eval"]=="rejected"
assert statuses["direct_framed_prune"]=="revoked"
assert "direct_var_eval" not in rv["runtime_policy"]["promoted"]
assert "direct_framed_prune" not in rv["runtime_policy"]["promoted"]

print("FLASH_CONTROLLER_TRANSITION_TESTS_PASS")
