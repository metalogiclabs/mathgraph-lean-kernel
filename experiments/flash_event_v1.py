#!/usr/bin/env python3
import json, sys
from pathlib import Path

SCHEMA="mathgraph.flash.event.v1"
KINDS={
    "observation",
    "causal_observation",
    "semantic_authority",
    "performance_authority",
    "current_revalidation",
    "obstruction_fingerprint",
    "candidate_pending",
}

def validate(e):
    if e.get("schema") != SCHEMA:
        raise ValueError("bad event schema")
    for k in ("id","kind","family","run"):
        if k not in e:
            raise ValueError(f"missing {k}")
    if e["kind"] not in KINDS:
        raise ValueError("unsupported event kind")
    if not isinstance(e["run"], int) or e["run"] <= 0:
        raise ValueError("run must be positive integer")

    if e["kind"] in {"semantic_authority","performance_authority","current_revalidation"}:
        if not e.get("capability_id"):
            raise ValueError("authority event missing capability_id")
        if not e.get("implementation_identity"):
            raise ValueError("authority event missing implementation_identity")

    if e["kind"] == "semantic_authority":
        if e.get("semantic_scope") != "409_current_arena_exports":
            raise ValueError("semantic authority scope is not full current Arena")
        if e.get("semantic_pass") is not True:
            raise ValueError("semantic authority did not pass")

    if e["kind"] == "performance_authority":
        if e.get("performance_pass") is not True:
            raise ValueError("performance authority did not pass")

    if e["kind"] == "current_revalidation":
        if e.get("authority_join_verified") is not True:
            raise ValueError("current revalidation lacks verified authority join")
        if not isinstance(e.get("joined_from"), list) or len(e["joined_from"]) < 2:
            raise ValueError("current revalidation missing joined_from provenance")
    return e

def canonical(e):
    return json.dumps(e, sort_keys=True, separators=(",",":"))

def ingest(ledger,event):
    validate(event)
    events=ledger.setdefault("events",[])
    old=next((x for x in events if x.get("id")==event["id"]),None)
    if old is not None:
        # Legacy ledger events need not carry the v1 envelope. An event id may
        # never silently change meaning: exact normalized payload is idempotent,
        # anything else is an explicit conflict.
        if canonical(old) == canonical(event):
            return "duplicate-identical"
        raise ValueError(f"conflicting event id: {event['id']}")
    events.append(event)
    return "appended"

def main():
    if len(sys.argv)!=4:
        raise SystemExit("usage: flash_event_v1.py ledger.json event.json output.json")
    lp,ep,op=map(Path,sys.argv[1:])
    ledger=json.loads(lp.read_text())
    event=json.loads(ep.read_text())
    status=ingest(ledger,event)
    op.write_text(json.dumps(ledger,indent=2,sort_keys=False)+"\n")
    print("FLASH_EVENT_INGEST_PASS")
    print("STATUS="+status)
    print("EVENT_ID="+event["id"])

if __name__=="__main__":
    main()
