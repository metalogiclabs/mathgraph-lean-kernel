#!/usr/bin/env python3
import argparse, json
from pathlib import Path

SCHEMA="mathgraph.flash.event.v1"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--kind",choices=["semantic_authority","performance_authority"],required=True)
    p.add_argument("--id",required=True)
    p.add_argument("--family",required=True)
    p.add_argument("--capability-id",required=True)
    p.add_argument("--run",type=int,required=True)
    p.add_argument("--implementation-identity",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--semantic-scope")
    p.add_argument("--semantic-pass",action="store_true")
    p.add_argument("--performance-pass",action="store_true")
    p.add_argument("--observations-json")
    a=p.parse_args()

    event={
        "schema":SCHEMA,
        "id":a.id,
        "kind":a.kind,
        "family":a.family,
        "run":a.run,
        "capability_id":a.capability_id,
        "implementation_identity":a.implementation_identity,
    }
    if a.kind=="semantic_authority":
        event["semantic_scope"]=a.semantic_scope
        event["semantic_pass"]=a.semantic_pass
        if event["semantic_scope"]!="409_current_arena_exports" or event["semantic_pass"] is not True:
            raise SystemExit("semantic authority requires full 409 scope and pass")
    else:
        event["performance_pass"]=a.performance_pass
        if event["performance_pass"] is not True:
            raise SystemExit("performance authority requires pass")
        if a.observations_json:
            event["observations"]=json.loads(Path(a.observations_json).read_text())

    Path(a.out).write_text(json.dumps(event,indent=2,sort_keys=True)+"\n")
    print("FLASH_AUTHORITY_EVENT_EMIT_PASS")
    print("EVENT_ID="+event["id"])

if __name__=="__main__":
    main()
