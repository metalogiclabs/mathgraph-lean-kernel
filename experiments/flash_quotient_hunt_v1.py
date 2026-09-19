#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

SEM_EQ={"EQ","EQ_FOCUSED","EQ_MATHLIB_REPLAY","EQ_PROBES"}
PREF_PASS={"PASS","PASS_NATIVE_RANK_UNKNOWN"}

def current_compatible(row,current):
    req=set(row.get("requires",[]))
    conflicts=set(row.get("conflicts",[]))
    cur=set(current)
    return req.issubset(cur) and not (conflicts & cur)

def next_action(row,current):
    auth=row["authority"]
    compatible=current_compatible(row,current)

    if not compatible:
        return {
            "id":row["id"],
            "epistemic":"DIST_CONTEXT",
            "action":"RETAIN_SEPARATOR",
            "reason":"current present violates applicability context",
        }

    sem=auth.get("semantic","UNKNOWN")
    cong=auth.get("congruence","UNKNOWN")
    pref=auth.get("preference","UNKNOWN")

    if sem=="UNKNOWN":
        return {"id":row["id"],"epistemic":"UNKNOWN","action":"MEASURE_EQUIVALENCE","reason":"semantic interchangeability not yet warranted"}
    if sem.startswith("DIST"):
        return {"id":row["id"],"epistemic":"DIST","action":"MINIMIZE_SEPARATOR","reason":"semantic separator exists"}
    if sem not in SEM_EQ:
        return {"id":row["id"],"epistemic":"UNKNOWN","action":"MEASURE_EQUIVALENCE","reason":f"unrecognized/partial semantic authority: {sem}"}

    if cong=="UNKNOWN":
        return {"id":row["id"],"epistemic":"EQ","action":"MEASURE_RIGHT_CONGRUENCE","reason":"equivalence known but continuation safety not established"}
    if cong.startswith("DIST"):
        return {"id":row["id"],"epistemic":"DIST","action":"MINIMIZE_SEPARATOR","reason":"authorized continuation separates the quotient"}
    if cong!="PASS":
        return {"id":row["id"],"epistemic":"UNKNOWN","action":"MEASURE_RIGHT_CONGRUENCE","reason":f"partial congruence authority: {cong}"}

    if pref=="UNKNOWN" or pref=="PASS_NATIVE_RANK_UNKNOWN":
        return {"id":row["id"],"epistemic":"EQ","action":"MEASURE_ARENA_PREFERENCE","reason":"lawful quotient exists; cheapest representative not established"}
    if pref.startswith("REJECT"):
        return {"id":row["id"],"epistemic":"EQ","action":"RESERVE_LAWFUL_BUT_COSTLY","reason":"lawful representative is not preferred in current context"}
    if pref in PREF_PASS:
        if row.get("status")=="PROMOTED":
            return {"id":row["id"],"epistemic":"EQ","action":"KEEP_PROMOTED","reason":"warranted, congruent, preferred"}
        return {"id":row["id"],"epistemic":"EQ","action":"PROMOTE_CHEAPEST_REPRESENTATIVE","reason":"all quotient gates pass"}

    return {"id":row["id"],"epistemic":"UNKNOWN","action":"MEASURE_ARENA_PREFERENCE","reason":f"partial preference authority: {pref}"}

def priority(row,action):
    # Favor large measured basins, then actions closest to promotion.
    share=float(row.get("estimated_eval_share",row.get("estimated_self_cost_share",0.0)))
    reuse=float(row.get("estimated_reuse_hit_rate",0.0))
    size=max(share,reuse*0.05)
    rank={
        "PROMOTE_CHEAPEST_REPRESENTATIVE":0,
        "MEASURE_ARENA_PREFERENCE":1,
        "MEASURE_RIGHT_CONGRUENCE":2,
        "MEASURE_EQUIVALENCE":3,
        "MINIMIZE_SEPARATOR":4,
        "RETAIN_SEPARATOR":5,
        "RESERVE_LAWFUL_BUT_COSTLY":6,
        "KEEP_PROMOTED":7,
    }.get(action,9)
    return (rank,-size,row["id"])

def close(registry):
    current=registry["current_present"]
    rows=[]
    for row in registry["distinctions"]:
        d=next_action(row,current)
        d["hotspot"]=row["hotspot"]
        d["representative"]=row["representative"]
        d["status"]=row["status"]
        d["priority_key"]=priority(row,d["action"])
        rows.append(d)
    actionable=[r for r in rows if r["action"] not in {"KEEP_PROMOTED","RESERVE_LAWFUL_BUT_COSTLY","RETAIN_SEPARATOR"}]
    actionable.sort(key=lambda r:tuple(r["priority_key"]))
    selected=actionable[0] if actionable else None
    return {
        "schema":"mathgraph.flash.quotient-hunt-plan.v1",
        "current_present":current,
        "selected":selected,
        "rows":rows,
        "invariants":{
            "unknown_never_merged":all(not (r["epistemic"]=="UNKNOWN" and r["action"].startswith("PROMOTE")) for r in rows),
            "context_conflict_never_promoted":all(not (r["epistemic"]=="DIST_CONTEXT" and r["action"].startswith("PROMOTE")) for r in rows),
        }
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("registry",type=Path)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    reg=json.loads(a.registry.read_text())
    plan=close(reg)
    a.out.write_text(json.dumps(plan,indent=2,sort_keys=True)+"\n")
    print("FLASH_QUOTIENT_HUNT_PASS")
    print("CURRENT_PRESENT="+",".join(plan["current_present"]))
    if plan["selected"]:
        print("SELECTED_DISTINCTION="+plan["selected"]["id"])
        print("SELECTED_ACTION="+plan["selected"]["action"])
    else:
        print("SELECTED_DISTINCTION=none")
        print("SELECTED_ACTION=none")
    assert plan["invariants"]["unknown_never_merged"]
    assert plan["invariants"]["context_conflict_never_promoted"]

if __name__=="__main__":
    main()
