#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

ARENA_SHA="510fbfead6f02bed1a0179d01729a6ddf5bfd06d"
AUTHORITY=f"lean-kernel-arena@{ARENA_SHA}"
VERIFIER="arena409-native-ablation-framed-v1"
CAPABILITY_ID="lean:direct-framed-prune:v1"

def canonical(v):
    return json.dumps(v,sort_keys=True,separators=(",",":"))

def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()

def build_event(source_commit:str):
    if len(source_commit)!=40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise ValueError("source commit must be full SHA")
    evidence={
        "schema":"lean-qckn-direct-framed-prune-evidence-v1",
        "arena_sha":ARENA_SHA,
        "semantic":{"run":35404941215,"exports":409,"mismatches":0},
        "causal":{
            "run":35405256169,
            "mathlib_speedup":1.040781,
            "protected_regressions":[],
        },
        "interpretation":"historical direct-Framed repair revalidated in the direct-Var present",
    }
    cap={
        "capability_id":CAPABILITY_ID,
        "input_type":"lean-framed-prune",
        "output_type":"lean-framed-prune-result",
        "semantics":[["framed-prune","framed-direct-equivalent"]],
        "guard_inputs":["framed-prune"],
        "certificate_id":"run:35404941215+run:35405256169",
        "dependencies":["lean:direct-var:v1"],
        "authority_snapshot":AUTHORITY,
        "verifier_id":VERIFIER,
        "provenance_ids":[
            "run:35404941215",
            "run:35405256169",
        ],
        "cost":0,
    }
    payload={
        "capability":cap,
        "oracle":[["framed-prune","framed-direct-equivalent"]],
        "support_ids":["lean:direct-var:v1"],
        "origin":"lean",
    }
    event={
        "schema":"qckn-flash-external-event-v1",
        "event_id":CAPABILITY_ID,
        "event_kind":"capability_admission",
        "repository":"metalogiclabs/mathgraph-lean-kernel",
        "commit":source_commit,
        "authority_snapshot":AUTHORITY,
        "verifier_id":VERIFIER,
        "source_evidence_sha256":sha(canonical(evidence)),
        "payload":payload,
        "payload_sha256":sha(canonical(payload)),
    }
    return evidence,event

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--commit",required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    evidence,event=build_event(a.commit)
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"evidence.json").write_text(canonical(evidence))
    (a.out/"event.json").write_text(canonical(event))
    print("QCKN_FLASH_EVENT="+event["event_id"])
    print("QCKN_FLASH_EVENT_PAYLOAD_SHA256="+event["payload_sha256"])

if __name__=="__main__":
    main()
