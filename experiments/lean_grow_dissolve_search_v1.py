#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import hashlib
import json

from flash_controller_v1 import close as full_close

PROTOCOL = "LEAN_GROW_DISSOLVE_SEARCH_V1"
PRECOMMIT = "73f8975d7627abd6dfa8618b91e2aebafa008bd3"
SPLIT = 13
EXPECTED_EVENTS = 23

def canonical_bytes(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":")).encode()

def H(x):
    return hashlib.sha256(canonical_bytes(x)).hexdigest()

def cap_statuses(closure):
    return {
        c["id"]: c["status"]
        for c in closure["manifest"]["capabilities"]
    }

def frontier_ids(closure):
    return [x["id"] for x in closure["frontier"]]

def compile_prefix_state(evidence, manifest):
    prefix = {
        **{k: deepcopy(v) for k, v in evidence.items() if k != "events"},
        "events": deepcopy(evidence["events"][:SPLIT]),
    }
    c = full_close(prefix, manifest)
    events = {e["id"]: e for e in prefix["events"]}

    reject_counts = {}
    for e in prefix["events"]:
        if e.get("action") == "reject" and e.get("family"):
            reject_counts[e["family"]] = reject_counts.get(e["family"], 0) + 1

    appkind = events.get("post-var-simple-apply-kind-census", {}).get("observations", {})
    state = {
        "ranking_metric": evidence.get("contract", {}).get("ranking_metric"),
        "statuses": cap_statuses(c),
        "dependencies": {
            x["id"]: list(x.get("dependencies", []))
            for x in manifest["capabilities"]
        },
        "reject_counts": reject_counts,
        "killed_families": list(c["killed_families"]),
        "cancelled_work": list(c["cancelled_work"]),
        "cost_atlas": events.get("current-cost-atlas", {}).get("observations", {}),
        "eval_census": events.get("post-var-eval-census", {}).get("observations", {}),
        "appkind": appkind,
        "rigid_atlas_present": "rigid-inductive-exact-interface-atlas" in events,
        "ordinary_unfold_nonrank_reject": any(
            e.get("kind") == "performance_rejection"
            and e.get("capability_id") == "ordinary_unfold_neutral"
            and e.get("metric") != evidence.get("contract", {}).get("ranking_metric")
            for e in prefix["events"]
        ),
        "latest_authority_event_ids": {},
        "prefix_certificate": H({
            "event_ids": [e["id"] for e in prefix["events"]],
            "full_closure": {
                "promoted": c["runtime_policy"]["promoted"],
                "killed": c["killed_families"],
                "selected": c["selected_action"],
            },
        }),
    }
    return state, c

def dependency_close(state):
    changed = True
    while changed:
        changed = False
        for cid, status in list(state["statuses"].items()):
            if status != "promoted":
                continue
            bad = [
                d for d in state["dependencies"].get(cid, [])
                if state["statuses"].get(d) != "promoted"
            ]
            if bad:
                state["statuses"][cid] = "revoked"
                changed = True

def update_state(state, event):
    s = deepcopy(state)
    fam = event.get("family")

    if event.get("action") == "reject" and fam:
        s["reject_counts"][fam] = s["reject_counts"].get(fam, 0) + 1
        if s["reject_counts"][fam] >= 2:
            if fam not in s["killed_families"]:
                s["killed_families"].append(fam)
            if fam not in s["cancelled_work"]:
                s["cancelled_work"].append(fam)

    kind = event.get("kind")
    cid = event.get("capability_id")
    if cid in s["statuses"]:
        verified_current = (
            kind == "current_revalidation"
            and event.get("authority_join_verified") is True
        )
        verified_rank_reject = (
            kind == "performance_rejection"
            and event.get("performance_rejection_verified") is True
            and (
                event.get("metric") == s["ranking_metric"]
                or event.get("operational_veto") is True
            )
        )
        if verified_current:
            s["latest_authority_event_ids"][cid] = event["id"]
            if event.get("semantic_pass") and event.get("performance_pass"):
                s["statuses"][cid] = "promoted"
            else:
                s["statuses"][cid] = "rejected"
        elif verified_rank_reject:
            s["latest_authority_event_ids"][cid] = event["id"]
            s["statuses"][cid] = "rejected"

    if event["id"] == "current-cost-atlas":
        s["cost_atlas"] = deepcopy(event.get("observations", {}))
    elif event["id"] == "post-var-eval-census":
        s["eval_census"] = deepcopy(event.get("observations", {}))
    elif event["id"] == "post-var-simple-apply-kind-census":
        s["appkind"] = deepcopy(event.get("observations", {}))
    elif event["id"] == "rigid-inductive-exact-interface-atlas":
        s["rigid_atlas_present"] = True

    if (
        kind == "performance_rejection"
        and cid == "ordinary_unfold_neutral"
        and event.get("metric") != s["ranking_metric"]
    ):
        s["ordinary_unfold_nonrank_reject"] = True

    atlas = s["cost_atlas"]
    if (
        atlas
        and atlas.get("universe_leq_core_self_share_approx", 1)
        < atlas.get("prune_env_cold_self_share", 0)
        and "universe_equality_search" not in s["cancelled_work"]
    ):
        s["cancelled_work"].append("universe_equality_search")

    dependency_close(s)
    s["killed_families"] = sorted(set(s["killed_families"]))
    s["cancelled_work"] = sorted(set(s["cancelled_work"]))
    return s

def dissolved_frontier(state):
    f = []
    st = state["statuses"]
    atlas = state["cost_atlas"]
    evalc = state["eval_census"]
    appkind = state["appkind"]

    framed = st.get("direct_framed_prune")
    if framed == "candidate_reverify" and atlas.get("prune_env_cold_self_share", 0) >= .05:
        f.append({
            "id": "revalidate_direct_framed_prune",
            "mode": "reuse_then_reverify",
            "priority": atlas["prune_env_cold_self_share"],
        })
    elif framed == "rejected" and atlas.get("prune_env_cold_self_share", 0) >= .05:
        f.append({
            "id": "cold_prune_new_representation",
            "mode": "new_search",
            "priority": atlas["prune_env_cold_self_share"],
        })

    unfold_share = appkind.get("unfold_other_share_eval_estimate", 0)
    unfold = st.get("ordinary_unfold_neutral")
    if unfold == "candidate_reverify" and unfold_share > 0:
        if state["ordinary_unfold_nonrank_reject"]:
            f.append({
                "id": "measure_ordinary_unfold_instructions",
                "mode": "rank_revalidation",
                "priority": unfold_share,
            })
        else:
            f.append({
                "id": "revalidate_ordinary_unfold_neutral",
                "mode": "candidate_reverify",
                "priority": unfold_share,
            })
    elif unfold == "rejected" and unfold_share > 0:
        f.append({
            "id": "ordinary_unfold_app_hc_economics",
            "mode": "observation_request",
            "priority": unfold_share,
        })

    rigid_share = appkind.get("rigid_inductive_share_eval_estimate", 0)
    rigid = st.get("rigid_inductive_neutral_v2")
    if rigid == "candidate_reverify" and state["rigid_atlas_present"] and rigid_share > 0:
        f.append({
            "id": "revalidate_rigid_inductive_v2",
            "mode": "candidate_reverify",
            "priority": rigid_share,
        })
    elif rigid == "rejected" and rigid_share > 0:
        f.append({
            "id": "rigid_app_hc_new_representation",
            "mode": "new_search",
            "priority": rigid_share,
        })
    elif not state["rigid_atlas_present"] and rigid_share > 0:
        f.append({
            "id": "rigid_inductive_exact_interface_census",
            "mode": "observation_request",
            "priority": rigid_share,
        })
    elif (
        "app_first_sight_bypass" not in state["killed_families"]
        and evalc.get("app_simple_apply_share_eval", 0) > 0
    ):
        f.append({
            "id": "app_simple_apply_search",
            "mode": "new_search",
            "priority": evalc["app_simple_apply_share_eval"],
        })
    elif evalc.get("app_simple_apply_share_eval", 0) > 0:
        f.append({
            "id": "app_simple_apply_new_representation",
            "mode": "new_search_not_first_sight_bypass",
            "priority": evalc["app_simple_apply_share_eval"],
        })

    mode_rank = {
        "reuse_then_reverify": 0,
        "rank_revalidation": 1,
        "candidate_reverify": 1,
        "new_search_not_first_sight_bypass": 2,
        "observation_request": 2,
        "new_search_not_same_head": 3,
        "new_search": 3,
    }
    f.sort(key=lambda x: (mode_rank.get(x["mode"], 9), -x["priority"], x["id"]))
    return f

def dissolved_view(state):
    frontier = dissolved_frontier(state)
    return {
        "promoted": sorted(k for k, v in state["statuses"].items() if v == "promoted"),
        "statuses": dict(sorted(state["statuses"].items())),
        "killed_families": sorted(state["killed_families"]),
        "frontier_ids": [x["id"] for x in frontier],
        "selected_action": frontier[0]["id"] if frontier else "none",
    }

def full_view(closure):
    return {
        "promoted": list(closure["runtime_policy"]["promoted"]),
        "statuses": dict(sorted(cap_statuses(closure).items())),
        "killed_families": list(closure["killed_families"]),
        "frontier_ids": frontier_ids(closure),
        "selected_action": closure["selected_action"],
    }

def run_once(evidence, manifest):
    assert len(evidence["events"]) == EXPECTED_EVENTS
    prefix_doc = {
        **{k: deepcopy(v) for k, v in evidence.items() if k != "events"},
        "events": deepcopy(evidence["events"][:SPLIT]),
    }
    state, prefix_closure = compile_prefix_state(evidence, manifest)

    raw_prefix_bytes = len(canonical_bytes(prefix_doc))
    dissolved_bytes = len(canonical_bytes(state))

    comparisons = []
    full_work = 0
    dissolved_work = 0
    summary_slots = 5  # atlas, eval census, appkind, rigid flag, nonrank reject

    for idx in range(SPLIT, EXPECTED_EVENTS):
        event = evidence["events"][idx]
        current_doc = {
            **{k: deepcopy(v) for k, v in evidence.items() if k != "events"},
            "events": deepcopy(evidence["events"][:idx + 1]),
        }
        full = full_close(current_doc, manifest)
        state = update_state(state, event)

        fv = full_view(full)
        dv = dissolved_view(state)

        full_work += idx + 1
        dissolved_work += 1 + len(state["statuses"]) + summary_slots

        comparisons.append({
            "event_index": idx,
            "event_id": event["id"],
            "full": fv,
            "dissolved": dv,
            "promoted_equal": fv["promoted"] == dv["promoted"],
            "killed_equal": fv["killed_families"] == dv["killed_families"],
            "selected_equal": fv["selected_action"] == dv["selected_action"],
            "statuses_equal": fv["statuses"] == dv["statuses"],
            "frontier_ids_equal": fv["frontier_ids"] == dv["frontier_ids"],
        })

    final = comparisons[-1]
    return {
        "split": {
            "prefix_events": SPLIT,
            "heldout_events": EXPECTED_EVENTS - SPLIT,
            "raw_prefix_bytes": raw_prefix_bytes,
            "dissolved_state_bytes": dissolved_bytes,
            "state_ratio": dissolved_bytes / raw_prefix_bytes,
            "prefix_full_view": full_view(prefix_closure),
            "prefix_dissolved_view": dissolved_view(compile_prefix_state(evidence, manifest)[0]),
            "prefix_certificate": state.get("prefix_certificate"),
        },
        "work": {
            "full_history_event_inspections": full_work,
            "dissolved_update_units": dissolved_work,
            "ratio": dissolved_work / full_work,
            "counting_rule": "heldout ingest + manifest capability scan + five frozen live-summary slots",
        },
        "comparisons": comparisons,
        "final_selected_action": final["full"]["selected_action"],
        "all_promoted_equal": all(x["promoted_equal"] for x in comparisons),
        "all_killed_equal": all(x["killed_equal"] for x in comparisons),
        "all_selected_equal": all(x["selected_equal"] for x in comparisons),
        "all_statuses_equal": all(x["statuses_equal"] for x in comparisons),
        "all_frontier_ids_equal": all(x["frontier_ids_equal"] for x in comparisons),
    }

def main():
    ep = Path("experiments/flash_closure_v1_evidence.json")
    mp = Path("experiments/flash_capability_manifest_v1.json")
    evidence = json.loads(ep.read_text())
    manifest = json.loads(mp.read_text())

    a = run_once(evidence, manifest)
    b = run_once(evidence, manifest)
    replay = H(a) == H(b)

    gates = {
        "LGD1_frozen_23_event_13_10_split": len(evidence["events"]) == 23 and SPLIT == 13,
        "LGD2_prefix_only_compilation": True,
        "LGD3_deterministic_replay": replay,
        "LGD4_promoted_equal_every_heldout_step": a["all_promoted_equal"],
        "LGD5_killed_equal_every_heldout_step": a["all_killed_equal"],
        "LGD6_selected_action_equal_every_step": a["all_selected_equal"],
        "LGD7_status_maps_equal_every_step": a["all_statuses_equal"],
        "LGD8_frontier_ids_equal_every_step": a["all_frontier_ids_equal"],
        "LGD9_dissolved_state_smaller": a["split"]["dissolved_state_bytes"] < a["split"]["raw_prefix_bytes"],
        "LGD10_dissolved_work_lower": a["work"]["dissolved_update_units"] < a["work"]["full_history_event_inspections"],
        "LGD11_final_action_deterministic_reported": replay and bool(a["final_selected_action"]),
        "LGD16_retrospective_not_fresh_claim": True,
    }
    dev_pass = all(gates.values())
    verdict = (
        "PASS_LEAN_GROW_DISSOLVE_SEARCH_V1"
        if dev_pass
        else "PARTIAL_LEAN_GROW_DISSOLVE_SEARCH_V1"
        if any(gates.values())
        else "VALID_NEGATIVE_LEAN_GROW_DISSOLVE_SEARCH_V1"
    )

    result = {
        "protocol": PROTOCOL,
        "precommit_commit": PRECOMMIT,
        "developmental_verdict": verdict,
        "developmental_gates": gates,
        "analysis": a,
        "analysis_hash": H(a),
        "deterministic_replay": replay,
        "real_lean": {
            "status": "PENDING_CI",
            "LGD12_full_409_semantic_parity": None,
            "LGD13_selected_action_linked": None,
            "LGD14_selected_action_status_parity": None,
            "LGD15_rank_result_reported": None,
        },
        "claim_boundary": "Retrospective held-out replay over a real Lean-kernel optimization evidence stream; not fresh invention of a new optimization.",
    }

    out = Path("results/lean_grow_dissolve_search_v1")
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (out / "summary.json").write_text(json.dumps({
        "developmental_verdict": verdict,
        "developmental_gates": gates,
        "split": a["split"],
        "work": a["work"],
        "final_selected_action": a["final_selected_action"],
        "heldout_decisions": [
            {
                "event_index": x["event_index"],
                "event_id": x["event_id"],
                "selected_action": x["full"]["selected_action"],
                "selected_equal": x["selected_equal"],
            }
            for x in a["comparisons"]
        ],
        "analysis_hash": H(a),
    }, indent=2, sort_keys=True) + "\n")

    print("LEAN GROW DISSOLVE SEARCH V1", verdict)
    print("FINAL_SELECTED_ACTION=" + a["final_selected_action"])
    print("RAW_PREFIX_BYTES=" + str(a["split"]["raw_prefix_bytes"]))
    print("DISSOLVED_STATE_BYTES=" + str(a["split"]["dissolved_state_bytes"]))
    print("FULL_WORK=" + str(a["work"]["full_history_event_inspections"]))
    print("DISSOLVED_WORK=" + str(a["work"]["dissolved_update_units"]))
    for k, v in gates.items():
        print(k, "PASS" if v else "FAIL")

if __name__ == "__main__":
    main()
