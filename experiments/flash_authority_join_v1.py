#!/usr/bin/env python3
import json, sys
from pathlib import Path

SCHEMA="mathgraph.flash.authority-join.v1"

def join(semantic, performance):
    required=("capability_id","implementation_identity")
    for x in (semantic, performance):
        for k in required:
            if k not in x:
                raise ValueError(f"missing {k}")

    if semantic["capability_id"] != performance["capability_id"]:
        raise ValueError("capability mismatch")
    if semantic["implementation_identity"] != performance["implementation_identity"]:
        raise ValueError("implementation mismatch")
    if semantic.get("semantic_scope") != "409_current_arena_exports":
        raise ValueError("insufficient semantic scope")
    if semantic.get("semantic_pass") is not True:
        raise ValueError("semantic authority did not pass")
    if performance.get("performance_pass") is not True:
        raise ValueError("performance authority did not pass")

    return {
        "id": f"{semantic['capability_id']}-joined-authority",
        "kind": "current_revalidation",
        "capability_id": semantic["capability_id"],
        "family": semantic.get("family") or performance.get("family"),
        "run": performance["run"],
        "semantic_run": semantic["run"],
        "semantic_scope": semantic["semantic_scope"],
        "semantic_pass": True,
        "performance_pass": True,
        "implementation_identity": semantic["implementation_identity"],
        "authority_join_verified": True,
        "joined_from": [semantic["id"], performance["id"]],
        "performance": performance.get("observations", {}),
    }

def main():
    if len(sys.argv)!=4:
        raise SystemExit("usage: flash_authority_join_v1.py semantic.json performance.json out.json")
    sp,pp,op=map(Path,sys.argv[1:])
    out=join(json.loads(sp.read_text()),json.loads(pp.read_text()))
    op.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print("FLASH_AUTHORITY_JOIN_PASS")
    print("CAPABILITY="+out["capability_id"])
    print("IMPLEMENTATION="+out["implementation_identity"])

if __name__=="__main__":
    main()
