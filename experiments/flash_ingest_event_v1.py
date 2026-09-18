#!/usr/bin/env python3
import json, sys
from pathlib import Path

SCHEMA="mathgraph.flash.verification-event.v1"

def main():
    if len(sys.argv)!=4:
        raise SystemExit("usage: flash_ingest_event_v1.py evidence.json event.json out.json")
    ep,vp,op=map(Path,sys.argv[1:])
    evidence=json.loads(ep.read_text())
    ev=json.loads(vp.read_text())
    assert ev.get("schema")==SCHEMA
    for k in ("event_id","kind","capability_id","run","semantic_pass","performance_pass"):
        assert k in ev, k
    assert ev["kind"]=="current_revalidation"
    ids={e["id"] for e in evidence["events"]}
    assert ev["event_id"] not in ids, "duplicate event"
    event={
        "id":ev["event_id"],
        "kind":"current_revalidation",
        "capability_id":ev["capability_id"],
        "run":ev["run"],
        "semantic_pass":bool(ev["semantic_pass"]),
        "performance_pass":bool(ev["performance_pass"]),
    }
    for k in ("mathlib_speedup","protected_regressions","authority","notes"):
        if k in ev:
            event[k]=ev[k]
    out=dict(evidence)
    out["events"]=list(evidence["events"])+[event]
    op.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print("FLASH_EVENT_INGESTED",event["id"],event["capability_id"])

if __name__=="__main__":
    main()
