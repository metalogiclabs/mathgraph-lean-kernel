#!/usr/bin/env python3
import importlib.util,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("flash_index",ROOT/"experiments/flash_index_v1.py")
fi=importlib.util.module_from_spec(spec); spec.loader.exec_module(fi)
m=json.loads((ROOT/"experiments/flash_capability_manifest_v1.json").read_text())
e=json.loads((ROOT/"experiments/flash_closure_v1_evidence.json").read_text())
idx=fi.build(m,e)

assert set(fi.impacted(idx,"eval_dispatch"))=={"direct_var_eval","direct_framed_prune","ordinary_unfold_neutral"}
assert set(fi.impacted(idx,"cold_prune"))=={"direct_framed_prune"}
assert set(fi.impacted(idx,"app_simple_apply"))=={"ordinary_unfold_neutral"}
assert set(fi.impacted(idx,"beta"))=={"r1_recurrent_beta"}
assert set(fi.impacted(idx,"eval"))=={"direct_var_eval","direct_framed_prune","ordinary_unfold_neutral","r1_recurrent_beta"}

assert "app_first_sight_bypass" in idx["killed_families"]
assert "same_head_unfold_continuation" in idx["killed_families"]

# A direct-Var evidence mutation must conservatively wake its dependents.
ev=idx["events"]["direct-var"]
assert set(ev["affected_capabilities"])=={"direct_var_eval","direct_framed_prune","ordinary_unfold_neutral"}

print("FLASH_IMPACT_INDEX_TESTS_PASS")
