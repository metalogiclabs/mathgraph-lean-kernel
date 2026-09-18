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

    changed = True
    gen = 0
    while changed:
        gen += 1
        changed = False

        # Promote only evidence explicitly admitted by authority.
        for e in evidence["events"]:
            cid = e.get("capability_id") or {
                "direct-var": "direct_var_eval",
                "cold-prune-direct-v93": "direct_framed_prune",
            }.get(e["id"])
            if not cid or cid not in caps:
                continue
            if e.get("action") == "promote" and e.get("semantic_pass"):
                if caps[cid]["status"] != "promoted":
                    old = caps[cid]["status"]
                    caps[cid]["status"] = "promoted"
                    trace.append([gen,"PROMOTE",cid,old])
                    changed = True

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

        # Candidate capability revalidation: only current-present authority can promote it.
        for e in evidence["events"]:
            if e.get("kind") != "current_revalidation":
                continue
            cid = e["capability_id"]
            c = caps[cid]
            if e.get("semantic_pass") and e.get("performance_pass"):
                if c["status"] != "promoted":
                    old=c["status"]; c["status"]="promoted"
                    c.setdefault("evidence",{})["current_revalidation"] = e["run"]
                    trace.append([gen,"PROMOTE_REVALIDATED",cid,old])
                    changed=True
            else:
                if c["status"] not in ("rejected","revoked"):
                    old=c["status"]; c["status"]="rejected"
                    trace.append([gen,"REJECT_REVALIDATED",cid,old])
                    changed=True

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
    if caps.get("direct_framed_prune",{}).get("status") != "promoted" and atlas.get("prune_env_cold_self_share",0) >= .05:
        frontier.append({
            "id":"revalidate_direct_framed_prune",
            "mode":"reuse_then_reverify",
            "priority": atlas["prune_env_cold_self_share"],
            "reason":"current high-cost residual matches previously verified repair family",
        })
    if "app_first_sight_bypass" not in killed_families and evalc.get("app_simple_apply_share_eval",0) > 0:
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

    # Flash acquisition economics: already-verified reusable capability is cheaper
    # than opening a new search, so close reusable work first when both remain live.
    mode_rank={"reuse_then_reverify":0,"new_search_not_first_sight_bypass":1,"new_search":1}
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

pub(crate) const PROMOTED_CAPABILITY_IDS: &[&str] = &[
%s
];
""" % (
        "true" if "direct_var_eval" in promoted else "false",
        "true" if "direct_framed_prune" in promoted else "false",
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
