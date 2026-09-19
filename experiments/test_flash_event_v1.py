#!/usr/bin/env python3
import importlib.util
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("fei",ROOT/"experiments/flash_event_v1.py")
fei=importlib.util.module_from_spec(spec); spec.loader.exec_module(fei)

base={"version":"test","events":[]}
event={
    "schema":"mathgraph.flash.event.v1",
    "id":"semantic-c1-r1",
    "kind":"semantic_authority",
    "family":"x",
    "run":1,
    "capability_id":"c1",
    "implementation_identity":"tree:abc",
    "semantic_scope":"409_current_arena_exports",
    "semantic_pass":True,
}

x=deepcopy(base)
assert fei.ingest(x,deepcopy(event))=="appended"
assert len(x["events"])==1
assert fei.ingest(x,deepcopy(event))=="duplicate-identical"
assert len(x["events"])==1

bad=deepcopy(event); bad["implementation_identity"]="tree:def"
try:
    fei.ingest(x,bad)
except ValueError as e:
    assert "conflicting event id" in str(e)
else:
    raise AssertionError("conflicting event was accepted")

bad_scope=deepcopy(event); bad_scope["id"]="bad-scope"; bad_scope["semantic_scope"]="focused_panel_exact_parity"
try:
    fei.ingest(deepcopy(base),bad_scope)
except ValueError as e:
    assert "scope" in str(e)
else:
    raise AssertionError("partial semantic authority was accepted")

joined={
    "schema":"mathgraph.flash.event.v1",
    "id":"joined-c1",
    "kind":"current_revalidation",
    "family":"x",
    "run":2,
    "capability_id":"c1",
    "implementation_identity":"tree:abc",
    "semantic_pass":True,
    "performance_pass":True,
    "authority_join_verified":True,
    "joined_from":["semantic-c1-r1","performance-c1-r2"],
}
assert fei.ingest(deepcopy(base),joined)=="appended"

print("FLASH_EVENT_INGEST_TESTS_PASS")
