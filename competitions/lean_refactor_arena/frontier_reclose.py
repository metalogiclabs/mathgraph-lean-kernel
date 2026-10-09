#!/usr/bin/env python3
"""Admission-first proof frontier selection and minimal JSONL reclosure.

The theorem statement and every required version are hard constraints.
Length and heartbeats are *only* optimization costs among candidates whose
exact source SHA and full verifier evidence match. Unknown != rejected.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def _objective_from_costs(length: int, heartbeat: int, ref_length: int, ref_hb: int) -> float:
    return round((ref_length - length) / ref_length * 100, 2) + round(
        (ref_hb - heartbeat) / ref_hb * 100, 2
    )


def _admission(
    candidate: dict[str, Any],
    measurement: dict[str, Any] | None,
    expected_name: str,
    versions: set[str],
    public_sha: str,
) -> dict[str, str]:
    """Bind the claim to source bytes, environment, and complete tested versions."""
    if measurement is None:
        return {"status": "UNKNOWN", "reason": "missing measurement"}
    if measurement.get("name") != expected_name or candidate.get("name") != expected_name:
        return {"status": "REJECTED", "reason": "wrong theorem name"}
    if measurement.get("compiled") is False or measurement.get("statement_ok") is False:
        return {"status": "REJECTED", "reason": "compiler/statement rejection"}
    if measurement.get("forbidden") or measurement.get("extra_toplevel_decls"):
        return {"status": "REJECTED", "reason": "forbidden or additional declaration"}
    if any(v is False for v in (measurement.get("compat") or {}).values()):
        return {"status": "REJECTED", "reason": "explicit protected version failure"}
    pv = measurement.get("per_version") or []
    if any(p.get("tested") is True and p.get("ok") is False for p in pv):
        return {"status": "REJECTED", "reason": "explicit per-version rejection"}
    proof = candidate.get("proof")
    if not isinstance(proof, str) or not proof.strip():
        return {"status": "REJECTED", "reason": "empty proof"}
    digest = hashlib.sha256(proof.encode("utf-8")).hexdigest()
    if measurement.get("proof_sha256") != digest:
        return {"status": "UNKNOWN", "reason": "proof source not bound to measurement"}
    if measurement.get("public_harness_sha") != public_sha:
        return {"status": "UNKNOWN", "reason": "different verifier environment"}
    # Organizer releases may omit the derived all_versions summary. The
    # epistemic authority is the exact *positive* pinned per-version matrix,
    # not the mere presence of a summary boolean. An explicit false flag
    # always vetoes admission; absent is permitted only if the complete
    # version matrix and other source/cost gates below positively verify it.
    all_versions_flag = measurement.get("all_versions")
    if all_versions_flag is not None and all_versions_flag is not True:
        return {"status": "UNKNOWN", "reason": "explicit or malformed full-version flag"}
    compat = measurement.get("compat") or {}
    version_records = {x.get("version"): x for x in pv}
    if (set(compat) != versions or len(pv) != len(versions)
            or set(version_records) != versions):
        return {"status": "UNKNOWN", "reason": "required version coverage incomplete"}
    if any(compat[v] is not True or version_records[v].get("tested") is not True
           or version_records[v].get("ok") is not True for v in versions):
        return {"status": "UNKNOWN", "reason": "version not positively verified"}
    if (measurement.get("compiled") is not True or
            measurement.get("statement_ok") is not True or
            measurement.get("eligible") is not True or measurement.get("untested")):
        return {"status": "UNKNOWN", "reason": "incomplete admission certificate"}
    if measurement.get("survival_pct") != 100:
        return {"status": "UNKNOWN", "reason": "not all protected versions survive"}
    try:
        length, hb = int(measurement["length"]), int(measurement["heartbeats"])
        ref_length = int(measurement["reference_length"])
        ref_hb = int(measurement["reference_heartbeats"])
        objective = float(measurement["objective_sum_pct"])
        if not all(x > 0 for x in (length, hb, ref_length, ref_hb)):
            raise ValueError("invalid reference metric")
        if not math.isfinite(objective):
            raise ValueError("invalid objective")
        if abs(objective - _objective_from_costs(length, hb, ref_length, ref_hb)) > 0.021:
            return {"status": "UNKNOWN", "reason": "score does not match measured costs"}
    except (KeyError, ValueError, TypeError):
        return {"status": "UNKNOWN", "reason": "unbound cost measurements"}
    return {"status": "WARRANTED", "reason": "source and all required consequences reverified"}


def decide(
    candidates: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    *,
    expected_name: str,
    required_versions: list[str],
    expected_public_sha: str,
    incumbent_label: str,
) -> dict[str, Any]:
    """Choose the best *warranted* score while retaining the Pareto frontier."""
    if not expected_name or not expected_public_sha or not required_versions:
        raise ValueError("frozen theorem, pin, and versions are required")
    labels = [c.get("label") for c in candidates]
    if not labels or not all(isinstance(x, str) and x for x in labels) or len(set(labels)) != len(labels):
        raise ValueError("candidate labels must be nonblank and unique")
    score_labels = [m.get("candidate_label") for m in measurements]
    if len(score_labels) != len(set(score_labels)):
        raise ValueError("ambiguous measurement evidence")
    score_by_label = {m["candidate_label"]: m for m in measurements}
    required = set(required_versions)
    admission = {c["label"]: _admission(c, score_by_label.get(c["label"]), expected_name, required, expected_public_sha)
                 for c in candidates}
    if incumbent_label not in admission or admission[incumbent_label]["status"] != "WARRANTED":
        raise ValueError("incumbent lacks exact current warranty")
    viable = [score_by_label[label] for label, status in admission.items()
              if status["status"] == "WARRANTED"]
    frontier = [r for r in viable if not any(
        other is not r and
        int(other["length"]) <= int(r["length"]) and
        int(other["heartbeats"]) <= int(r["heartbeats"]) and
        (int(other["length"]) < int(r["length"]) or int(other["heartbeats"]) < int(r["heartbeats"]))
        for other in viable)]
    incumbent = score_by_label[incumbent_label]
    better = [r for r in frontier if float(r["objective_sum_pct"]) > float(incumbent["objective_sum_pct"]) + 1e-9]
    best = (max(better, key=lambda r: (float(r["objective_sum_pct"]),
                  -int(r["length"]), -int(r["heartbeats"]), r["candidate_label"]))
            if better else incumbent)
    return {
        "selected_label": best["candidate_label"],
        "objective_gain": round(float(best["objective_sum_pct"]) - float(incumbent["objective_sum_pct"]), 4),
        "frontier_labels": sorted(r["candidate_label"] for r in frontier),
        "admission": admission,
        "impact": ("selected proof -> packet row -> portfolio aggregate" if best is not incumbent
                   else "no active proof change"),
    }


def reclose_packet(
    packet: str,
    theorem: str,
    candidates: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    *,
    required_versions: list[str],
    expected_public_sha: str,
    incumbent_label: str,
) -> tuple[str, dict[str, Any]]:
    """Reform a single JSONL row only from a positively admitted improvement.

    The caller cannot supply an unaudited 'allowed' boolean: every change is
    bound to the verified candidate's exact bytes through decide().
    """
    decision = decide(candidates, measurements, expected_name=theorem,
                      required_versions=required_versions,
                      expected_public_sha=expected_public_sha,
                      incumbent_label=incumbent_label)
    if decision["objective_gain"] <= 0:
        return packet, decision
    selected_label = decision["selected_label"]
    if decision["admission"][selected_label]["status"] != "WARRANTED":
        raise ValueError("selected proof is not certified")
    selected_proof = next(c["proof"] for c in candidates if c["label"] == selected_label)
    lines = packet.splitlines(keepends=True)
    names = [json.loads(line)["name"] for line in lines if line.strip()]
    if len(names) != len(set(names)) or names.count(theorem) != 1:
        raise ValueError("packet lacks one unique target theorem")
    protected_incumbent = next(c["proof"] for c in candidates if c["label"] == incumbent_label)
    active = next(json.loads(line) for line in lines if line.strip() and json.loads(line)["name"] == theorem)
    if active.get("proof") != protected_incumbent:
        raise ValueError("packet theorem no longer matches the certified incumbent")
    out: list[str] = []
    for line in lines:
        if not line.strip():
            out.append(line)
            continue
        item = json.loads(line)
        if item["name"] == theorem:
            item["proof"] = selected_proof
            suffix = "\n" if line.endswith("\n") else ""
            out.append(json.dumps(item, ensure_ascii=False) + suffix)
        else:
            out.append(line)
    return "".join(out), decision
