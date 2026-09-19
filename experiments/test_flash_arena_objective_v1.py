#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("obj",ROOT/"experiments/flash_arena_objective_v1.py")
obj=importlib.util.module_from_spec(spec); spec.loader.exec_module(obj)

base={
    "wrong_accepts":0,"wrong_rejects":0,"declines":0,
    "mathlib_instructions":1000000,
}

# Mathlib instruction win dominates a modest secondary regression.
cand=dict(base,mathlib_instructions=980000,secondary_speedups={"cedar":0.9737})
ok,why=obj.performance_admission(cand,base)
assert ok and why=="arena_objective_pass"
assert obj.arena_better(cand,base)

# Any correctness regression is fatal even if much faster.
bad=dict(base,wrong_accepts=1,mathlib_instructions=500000)
ok,why=obj.performance_admission(bad,base)
assert not ok and why=="wrong_accept_regression"
assert not obj.arena_better(bad,base)

# Tiny instruction movement is treated as noise.
tiny=dict(base,mathlib_instructions=999000)
ok,why=obj.performance_admission(tiny,base)
assert not ok and why=="mathlib_gain_below_threshold"

# Catastrophic secondary behavior is an operational veto.
cat=dict(base,mathlib_instructions=950000,secondary_speedups={"cedar":0.5})
ok,why=obj.performance_admission(cat,base)
assert not ok and why.startswith("catastrophic_secondary_regression:")

print("FLASH_ARENA_OBJECTIVE_TESTS_PASS")
