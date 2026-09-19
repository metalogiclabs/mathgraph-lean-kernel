#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ACTIVE_COMMIT="17b88d3eb795be19cdcd909562e4ab2b5366ff5f"
ARENA_SHA="510fbfead6f02bed1a0179d01729a6ddf5bfd06d"
AUTHORITY=f"lean-kernel-arena@{ARENA_SHA}"
VERIFIER="arena409-native-ablation-callgrind-v2"


def canonical(v: object) -> str:
    return json.dumps(v,sort_keys=True,separators=(",",":"))


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def build_event(*,source_commit: str):
    if len(source_commit)!=40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise ValueError("source commit must be full SHA")

    evidence={
        "schema":"lean-qckn-ordinary-unfold-evidence-v1",
        "active_capability_commit":ACTIVE_COMMIT,
        "arena_sha":ARENA_SHA,
        "semantic":{
            "run":35409042523,
            "job":105804854792,
            "exports":409,
            "mismatches":0,
        },
        "native":{
            "run":35406159658,
            "job":105796414731,
            "ablated_wall_med_s":88.14,
            "candidate_wall_med_s":87.43,
            "wall_speedup":1.008121,
            "ablated_user_med_s":326.04,
            "candidate_user_med_s":323.82,
            "user_speedup":1.006856,
        },
        "callgrind":{
            "run":35409042523,
            "candidate_job":105804854776,
            "ablated_job":105804854807,
            "candidate_ir":805605976363,
            "ablated_ir":806322782813,
        },
    }
    evidence_text=canonical(evidence)

    cap={
        "capability_id":"lean:ordinary-unfold-neutral:v1",
        "input_type":"lean-simple-apply-unfold",
        "output_type":"lean-neutral-application",
        "semantics":[["ordinary-unfold","neutral-app-equivalent"]],
        "guard_inputs":["ordinary-unfold"],
        "certificate_id":"run:35409042523+run:35406159658",
        "dependencies":["lean:direct-var:v1"],
        "authority_snapshot":AUTHORITY,
        "verifier_id":VERIFIER,
        "provenance_ids":[
            f"commit:{ACTIVE_COMMIT}",
            "run:35406159658",
            "run:35409042523",
        ],
        "cost":0,
    }
    payload={
        "capability":cap,
        "oracle":[["ordinary-unfold","neutral-app-equivalent"]],
        "support_ids":["lean:direct-var:v1"],
        "origin":"lean",
    }
    event={
        "schema":"qckn-flash-external-event-v1",
        "event_id":"lean:ordinary-unfold-neutral:v1",
        "event_kind":"capability_admission",
        "repository":"metalogiclabs/mathgraph-lean-kernel",
        "commit":source_commit,
        "authority_snapshot":AUTHORITY,
        "verifier_id":VERIFIER,
        "source_evidence_sha256":_sha(evidence_text),
        "payload":payload,
        "payload_sha256":_sha(canonical(payload)),
    }
    return evidence,event


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--commit",required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    evidence,event=build_event(source_commit=a.commit)
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"evidence.json").write_text(canonical(evidence),encoding="utf-8")
    (a.out/"event.json").write_text(canonical(event),encoding="utf-8")
    print("QCKN_FLASH_EVENT="+event["event_id"])
    print("QCKN_FLASH_EVENT_PAYLOAD_SHA256="+event["payload_sha256"])


if __name__=="__main__":
    main()
