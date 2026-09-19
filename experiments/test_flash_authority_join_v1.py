#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("aj",ROOT/"experiments/flash_authority_join_v1.py")
aj=importlib.util.module_from_spec(spec); spec.loader.exec_module(aj)

semantic={
 "id":"s","kind":"semantic_authority","capability_id":"c","family":"f",
 "run":1,"semantic_scope":"409_current_arena_exports","semantic_pass":True,
 "implementation_identity":"abc",
}
performance={
 "id":"p","kind":"performance_authority","capability_id":"c","family":"f",
 "run":2,"performance_pass":True,"implementation_identity":"abc",
 "observations":{"speedup":1.04},
}
j=aj.join(semantic,performance)
assert j["authority_join_verified"] is True
assert j["semantic_run"]==1 and j["run"]==2
assert j["implementation_identity"]=="abc"

bad=dict(performance); bad["implementation_identity"]="def"
try:
    aj.join(semantic,bad)
except ValueError as e:
    assert "implementation mismatch" in str(e)
else:
    raise AssertionError("mismatched code was incorrectly joined")

bad_scope=dict(semantic); bad_scope["semantic_scope"]="focused_panel_exact_parity"
try:
    aj.join(bad_scope,performance)
except ValueError as e:
    assert "insufficient semantic scope" in str(e)
else:
    raise AssertionError("insufficient semantic scope was incorrectly joined")

print("FLASH_AUTHORITY_JOIN_TESTS_PASS")
