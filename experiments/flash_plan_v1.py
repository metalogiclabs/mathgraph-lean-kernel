#!/usr/bin/env python3
import json,sys
from pathlib import Path

def plan(closure,registry):
    if registry.get("schema")!="mathgraph.flash.action-registry.v1":
        raise ValueError("bad registry schema")
    action=closure.get("selected_action")
    if action=="none":
        return {"selected_action":"none","status":"fixed_point_no_work"}
    entry=registry.get("actions",{}).get(action)
    if entry is None:
        raise ValueError(f"unregistered Flash action: {action}")
    out={"selected_action":action,**entry}
    out["status"]="ready" if entry.get("prepared") else "unimplemented"
    return out

def main():
    if len(sys.argv)!=4:
        raise SystemExit("usage: flash_plan_v1.py closure.json registry.json out.json")
    cp,rp,op=map(Path,sys.argv[1:])
    out=plan(json.loads(cp.read_text()),json.loads(rp.read_text()))
    op.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print("FLASH_ACTION_PLAN_PASS")
    print("SELECTED_ACTION="+out["selected_action"])
    print("STATUS="+out["status"])

if __name__=="__main__":
    main()
