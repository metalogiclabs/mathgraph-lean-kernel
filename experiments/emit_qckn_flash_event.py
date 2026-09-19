#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ACTIVE_CAPABILITY_COMMIT = "74dc5ddb4584e1254f5687615e5b02795b8dc6f3"
ARENA_SHA = "510fbfead6f02bed1a0179d01729a6ddf5bfd06d"
AUTHORITY = f"lean-kernel-arena@{ARENA_SHA}"
VERIFIER = "arena409-native-ablation-callgrind-v1"


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _full_sha(value: str) -> bool:
    return len(value) == 40 and all(ch in "0123456789abcdef" for ch in value)


def build_event(*, source_commit: str) -> tuple[dict[str, object], dict[str, object]]:
    if not _full_sha(source_commit):
        raise ValueError("source commit must be full lowercase SHA")

    evidence: dict[str, object] = {
        "schema": "lean-qckn-direct-var-evidence-v1",
        "active_capability_commit": ACTIVE_CAPABILITY_COMMIT,
        "arena_sha": ARENA_SHA,
        "semantic": {
            "run": 35380841937,
            "run_head_sha": "fc1d88d0cae432da7da22c25785569240089fc7d",
            "exports": 409,
            "mismatches": 0,
        },
        "native": {
            "qualification_run": 35380563756,
            "job": 105715714333,
            "ablated_wall_med_s": 71.87,
            "candidate_wall_med_s": 70.45,
            "wall_speedup": 1.020156,
            "ablated_user_med_s": 235.38,
            "candidate_user_med_s": 232.07,
            "user_speedup": 1.014263,
        },
        "callgrind": {
            "qualification_run": 35380563756,
            "candidate_job": 105715714344,
            "ablated_job": 105715714369,
            "candidate_ir": 806955885977,
            "ablated_ir": 809001375586,
        },
    }
    evidence_text = canonical(evidence)

    capability = {
        "capability_id": "lean:direct-var:v1",
        "input_type": "lean-eval-var",
        "output_type": "lean-value",
        "semantics": [["var", "env-slot-value"]],
        "guard_inputs": ["var"],
        "certificate_id": "run:35380841937+jobs:105715714333,105715714344,105715714369",
        "dependencies": [],
        "authority_snapshot": AUTHORITY,
        "verifier_id": VERIFIER,
        "provenance_ids": [
            f"commit:{ACTIVE_CAPABILITY_COMMIT}",
            "run:35380841937",
            "run:35380563756",
        ],
        "cost": 0,
    }
    payload: dict[str, object] = {
        "capability": capability,
        "oracle": [["var", "env-slot-value"]],
        "support_ids": [],
        "origin": "lean",
    }
    event: dict[str, object] = {
        "schema": "qckn-flash-external-event-v1",
        "event_id": "lean:direct-var:v1",
        "event_kind": "capability_admission",
        "repository": "metalogiclabs/mathgraph-lean-kernel",
        "commit": source_commit,
        "authority_snapshot": AUTHORITY,
        "verifier_id": VERIFIER,
        "source_evidence_sha256": hashlib.sha256(evidence_text.encode()).hexdigest(),
        "payload": payload,
        "payload_sha256": hashlib.sha256(canonical(payload).encode()).hexdigest(),
    }
    return evidence, event


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    evidence, event = build_event(source_commit=args.commit)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "evidence.json").write_text(canonical(evidence), encoding="utf-8")
    (args.out / "event.json").write_text(canonical(event), encoding="utf-8")
    print("QCKN_FLASH_EVENT=lean:direct-var:v1")
    print("QCKN_FLASH_EVENT_PAYLOAD_SHA256=" + str(event["payload_sha256"]))


if __name__ == "__main__":
    main()
