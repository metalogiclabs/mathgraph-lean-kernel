#!/usr/bin/env python3
import hashlib, json, sys
from copy import deepcopy
from pathlib import Path

SCHEMA = "mathgraph.flash.controller.v1"

def canonical_bytes(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":")).encode()

def digest(x):
    return hashlib.sha256(canonical_bytes(x)).hexdigest()

def close(evidence, manifest):
    events = {e["id"]: e for e in evidence["events"]}
    m = deepcopy(manifest)
    caps = {c["id"]: c for c in m["capabilities"]}
    obs = {o["id"]: o for o in m.get("obstructions", [])}
    trace = []
    cancelled = set()
    killed_families = set()
    frontier = []

    # Collapse authority history to one current authority event per capability.
    # Event order is causal order in the evidence ledger: the latest verified
    # revalidation overrides older promotion evidence. History remains provenance,
    # but only the reduced current authority may mutate the compiled present.
    latest_decision = {}
    for e in evidence["events"]:
        kind=e.get("kind")
        verified = (
            (kind == "current_revalidation" and e.get("authority_join_verified") is True)
            or
            (kind == "performance_rejection" and e.get("performance_rejection_verified") is True)
        )
        if verified:
            cid=e["capability_id"]
            if cid in caps:
                latest_decision[cid]=e

    # Seed capabilities that have no newer verified current decision.
    for e in evidence["events"]:
        cid = e.get("capability_id") or {
            "direct-var": "direct_var_eval",
            "cold-prune-direct-v93": "direct_framed_prune",
        }.get(e["id"])
        if not cid or cid not in caps or cid in latest_decision:
            continue
        if e.get("action") == "promote" and e.get("semantic_pass"):
            old = caps[cid]["status"]
            if old != "promoted":
                caps[cid]["status"] = "promoted"
                trace.append([0,"PROMOTE_SEED",cid,old])

    # Apply the latest verified current decision exactly once.
    # A performance rejection is allowed to kill a candidate without claiming
    # a full semantic authority result: being slower is sufficient to reject it.
    for cid,e in latest_decision.items():
        c=caps[cid]
        old=c["status"]
        if e.get("kind") == "performance_rejection":
            c["status"]="rejected"
            c.setdefault("evidence",{})["current_performance_rejection"]=e["run"]
            if old != "rejected":
                trace.append([0,"REJECT_PERFORMANCE",cid,old])
        elif e.get("semantic_pass") and e.get("performance_pass"):
            c["status"] = "promoted"
            c.setdefault("evidence",{})["current_revalidation"] = e["run"]
            if old != "promoted":
                trace.append([0,"PROMOTE_REVALIDATED",cid,old])
        else:
            c["status"] = "rejected"
            if old != "rejected":
                trace.append([0,"REJECT_REVALIDATED",cid,old])

    changed = True
    gen = 0
    while changed:
        gen += 1
        changed = False

        # Rejected implementation families become obstructions/cancelled search.
        fam_rejects = {}
        for e in evidence["events"]:
            if e.get("action") == "reject":
                fam_rejects.setdefault(e.get("family",""), []).append(e)
        for fam,xs in fam_rejects.items():
            if fam and len(xs) >= 2 and fam not in killed_families:
                killed_families.add(fam)
                cancelled.add(fam)
                trace.append([gen,"KILL_FAMILY",fam])
                changed = True

        # Dependency closure / revocation.
        for cid,c in caps.items():
            if c["status"] != "promoted":
                continue
            bad=[d for d in c.get("dependencies",[]) if caps[d]["status"]!="promoted"]
            if bad:
                c["status"]="revoked"
                trace.append([gen,"REVOKE_DEPENDENCY",cid,bad])
                changed=True

        # Later global evidence cancels dominated investigation.
        atlas = events.get("current-cost-atlas",{}).get("observations",{})
        if atlas:
            if atlas.get("universe_leq_core_self_share_approx",1) < atlas.get("prune_env_cold_self_share",0):
                cancelled.add("universe_equality_search")

    # Derived live frontier after closure.
    atlas = events.get("current-cost-atlas",{}).get("observations",{})
    evalc = events.get("post-var-eval-census",{}).get("observations",{})
    framed_status = caps.get("direct_framed_prune",{}).get("status")
    if framed_status == "candidate_reverify" and atlas.get("prune_env_cold_self_share",0) >= .05:
        frontier.append({
            "id":"revalidate_direct_framed_prune",
            "mode":"reuse_then_reverify",
            "priority": atlas["prune_env_cold_self_share"],
            "reason":"current high-cost residual matches previously verified repair family",
        })
    elif framed_status == "rejected" and atlas.get("prune_env_cold_self_share",0) >= .05:
        frontier.append({
            "id":"cold_prune_new_representation",
            "mode":"new_search",
            "priority": atlas["prune_env_cold_self_share"],
            "reason":"current direct-Framed implementation was rejected; preserve residual but do not replay identical candidate",
        })
    appkind = events.get("post-var-simple-apply-kind-census",{}).get("observations",{})
    unfold_cap = caps.get("ordinary_unfold_neutral",{})
    unfold_share_eval = appkind.get("unfold_other_share_eval_estimate",0)

    if unfold_cap and unfold_cap.get("status") == "candidate_reverify" and unfold_share_eval > 0:
        frontier.append({
            "id":"revalidate_ordinary_unfold_neutral",
            "mode":"candidate_reverify",
            "priority": unfold_share_eval,
            "reason":"61.2% of simple-apply functions are ordinary Unfold; implemented neutral fast path awaits authority",
        })
    elif unfold_cap and unfold_cap.get("status") == "rejected" and unfold_share_eval > 0:
        frontier.append({
            "id":"ordinary_unfold_app_hc_economics",
            "mode":"observation_request",
            "priority": unfold_share_eval,
            "reason":"neutral dispatch rejected; function canonical=100%, argument canonical=90.0%, app_hc hit=43.95%; measure interning cost before new representation",
        })

    rigid_share_eval = appkind.get("rigid_inductive_share_eval_estimate",0)
    rigid_cap = caps.get("rigid_inductive_neutral_v2",{})
    rigid_atlas = events.get("rigid-inductive-exact-interface-atlas",{})
    if rigid_cap and rigid_cap.get("status") == "candidate_reverify" and rigid_atlas and rigid_share_eval > 0:
        frontier.append({
            "id":"revalidate_rigid_inductive_v2",
            "mode":"candidate_reverify",
            "priority": rigid_share_eval,
            "reason":"80M rigid-inductive simple apps; function canonical 100%, argument pointer-stable 93.7%, app_hc exact hit 51.5%",
        })
    elif rigid_cap and rigid_cap.get("status") == "rejected" and rigid_share_eval > 0:
        frontier.append({
            "id":"rigid_app_hc_new_representation",
            "mode":"new_search",
            "priority": rigid_share_eval,
            "reason":"rigid V2 rejected; retain exact-interface residual but do not replay identical dispatch specialization",
        })
    elif not rigid_atlas and rigid_share_eval > 0:
        frontier.append({
            "id":"rigid_inductive_exact_interface_census",
            "mode":"observation_request",
            "priority": rigid_share_eval,
            "reason":"V39 forbids generic digest reuse without exact structural equality",
        })
    elif "app_first_sight_bypass" not in killed_families and evalc.get("app_simple_apply_share_eval",0) > 0:
        frontier.append({
            "id":"app_simple_apply_search",
            "mode":"new_search",
            "priority": evalc["app_simple_apply_share_eval"],
        })
    elif evalc.get("app_simple_apply_share_eval",0) > 0:
        frontier.append({
            "id":"app_simple_apply_new_representation",
            "mode":"new_search_not_first_sight_bypass",
            "priority": evalc["app_simple_apply_share_eval"],
            "reason":"old first-sight family killed by two REDs",
        })

    # Flash acquisition economics: reuse verified knowledge before candidate
    # revalidation, and revalidate an existing candidate before opening new search.
    mode_rank={
        "reuse_then_reverify":0,
        "candidate_reverify":1,
        "new_search_not_first_sight_bypass":2,
        "observation_request":2,
        "new_search_not_same_head":3,
        "new_search":3,
    }
    frontier.sort(key=lambda x:(mode_rank.get(x["mode"],9),-x["priority"],x["id"]))

    # Runtime contains promoted only.
    promoted=sorted(c["id"] for c in caps.values() if c["status"]=="promoted")
    runtime = {
        "schema":"mathgraph.flash.runtime.v1",
        "promoted":promoted,
        "fallback":"conservative incumbent paths",
        "trusted_semantics":"unchanged",
    }

    result={
        "schema":SCHEMA,
        "fixed_point_generations":gen,
        "manifest":m,
        "runtime_policy":runtime,
        "cancelled_work":sorted(cancelled),
        "killed_families":sorted(killed_families),
        "frontier":frontier,
        "selected_action":frontier[0]["id"] if frontier else "none",
        "trace":trace,
    }
    return result

def emit_rust(runtime):
    promoted=set(runtime["promoted"])
    return """// @generated by experiments/flash_controller_v1.py
// Only externally promoted capabilities may be active here.

pub(crate) const DIRECT_VAR_EVAL: bool = %s;
pub(crate) const DIRECT_FRAMED_PRUNE: bool = %s;
pub(crate) const ORDINARY_UNFOLD_NEUTRAL: bool = %s;

pub(crate) const PROMOTED_CAPABILITY_IDS: &[&str] = &[
%s];
""" % (
        "true" if "direct_var_eval" in promoted else "false",
        "true" if "direct_framed_prune" in promoted else "false",
        "true" if "ordinary_unfold_neutral" in promoted else "false",
        "".join(f'    "{x}",\n' for x in sorted(promoted)),
    )

def main():
    if len(sys.argv) != 5:
        raise SystemExit("usage: flash_controller_v1.py evidence.json manifest.json out_dir runtime.rs")
    ep,mp,od,rp=map(Path,sys.argv[1:])
    evidence=json.loads(ep.read_text())
    manifest=json.loads(mp.read_text())
    out=close(evidence,manifest)
    od.mkdir(parents=True,exist_ok=True)
    (od/"closure.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    (od/"runtime-policy.json").write_text(json.dumps(out["runtime_policy"],indent=2,sort_keys=True)+"\n")
    (od/"frontier.json").write_text(json.dumps(out["frontier"],indent=2,sort_keys=True)+"\n")
    certificate={
        "schema":"mathgraph.flash.closure-certificate.v1",
        "evidence_sha256":digest(evidence),
        "input_manifest_sha256":digest(manifest),
        "closure_sha256":digest(out),
        "runtime_policy_sha256":digest(out["runtime_policy"]),
        "selected_action":out["selected_action"],
        "fixed_point_generations":out["fixed_point_generations"],
    }
    (od/"certificate.json").write_text(json.dumps(certificate,indent=2,sort_keys=True)+"\n")
    rp.write_text(emit_rust(out["runtime_policy"]))
    print("FLASH_CONTROLLER_FIXED_POINT")
    print("SELECTED_ACTION="+out["selected_action"])
    print("PROMOTED="+",".join(out["runtime_policy"]["promoted"]))
    print("CERTIFICATE_SHA256="+digest(certificate))

if __name__=="__main__":
    main()
