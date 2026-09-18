#!/usr/bin/env python3
import json
import sys
from pathlib import Path

def load(path):
    return json.loads(Path(path).read_text())

def add(s, x):
    if x in s:
        return False
    s.add(x)
    return True

def close(doc):
    events = {e["id"]: e for e in doc["events"]}
    by_family = {}
    for e in doc["events"]:
        by_family.setdefault(e.get("family",""), []).append(e)

    active = set()
    rejected = set()
    repair_rules = set()
    killed_families = set()
    cancelled = set()
    scheduled = set()
    trace = []

    changed = True
    generation = 0
    while changed:
        generation += 1
        changed = False

        # Evidence classification.
        for e in doc["events"]:
            action = e.get("action")
            if action == "promote" and e.get("semantic_pass"):
                if add(active, e["id"]):
                    trace.append([generation, "PROMOTE", e["id"]])
                    changed = True
            elif action == "reject":
                if add(rejected, e["id"]):
                    trace.append([generation, "REJECT", e["id"]])
                    changed = True
            elif action == "promote_repair_family":
                # Historical repair knowledge may be reused only if it was semantically
                # clean and beneficial on the declared family.
                if e.get("semantic_pass") and e.get("mathlib_delta_percent", 1.0) < 0:
                    key = f'{e["family"]}:{e["strategy"]}'
                    if add(repair_rules, key):
                        trace.append([generation, "COMPILE_REPAIR_RULE", key])
                        changed = True

        # Repeated failed variants kill a repair family, not just an individual branch.
        for fam, xs in by_family.items():
            bad = [x for x in xs if x.get("action") == "reject"]
            if len(bad) >= 2 and fam:
                if add(killed_families, fam):
                    trace.append([generation, "KILL_FAMILY", fam])
                    changed = True

        # Later global cost evidence reclassifies earlier residuals.
        atlas = events["current-cost-atlas"]["observations"]
        if events["r3c-universe-eq-cache"]["id"] in rejected:
            if atlas["universe_leq_core_self_share_approx"] < atlas["prune_env_cold_self_share"]:
                if add(cancelled, "universe_equality_search"):
                    trace.append([generation, "CANCEL", "universe_equality_search"])
                    changed = True

        # Direct Var changes the live eval frontier immediately.
        if "direct-var" in active:
            if add(cancelled, "var_dispatch_search"):
                trace.append([generation, "CANCEL", "var_dispatch_search"])
                changed = True

        # The post-Var app residual remains real, but old bypass strategies are dead.
        if "app_first_sight_bypass" in killed_families:
            if add(cancelled, "app_first_sight_bypass_family"):
                trace.append([generation, "CANCEL", "app_first_sight_bypass_family"])
                changed = True

        # Flash rule: if a live high-cost residual matches a previously verified repair
        # fingerprint, revive the repair as a transplant rather than rediscover it.
        cold = atlas["prune_env_cold_self_share"]
        fp = events["cold-prune-separator-v91"]["fingerprint"]
        rule = "cold_prune:direct_framed_prune"
        if cold >= 0.05 and fp["end_kind"] == "Framed" and rule in repair_rules:
            if add(scheduled, "transplant_direct_framed_prune_into_active_var"):
                trace.append([generation, "FLASH_REUSE", "transplant_direct_framed_prune_into_active_var"])
                changed = True

    # Frontier: only actions not discharged by closure.
    open_frontier = []
    if "transplant_direct_framed_prune_into_active_var" in scheduled:
        open_frontier.append({
            "action": "transplant_direct_framed_prune_into_active_var",
            "reason": "11.6% current Mathlib self-cost + exact historical separator + verified direct-only repair",
            "acquisition": "reuse_then_reverify",
            "historical_run": 34210623437,
            "current_cost_run": 35389603404,
        })
    # app_simple_apply stays unresolved, but do not replay killed repair families.
    open_frontier.append({
        "action": "app_simple_apply_new_representation_search",
        "reason": "16.91% of post-Var eval entries; prior first-sight bypass family killed",
        "acquisition": "new_search_required",
        "census_run": 35401942103,
    })

    # Cost-sensitive closure chooses verified reuse before new acquisition when both are live.
    selected = open_frontier[0]["action"] if open_frontier else "none"

    return {
        "version": doc["version"],
        "fixed_point_generations": generation,
        "active_capabilities": sorted(active),
        "compiled_repair_rules": sorted(repair_rules),
        "rejected_candidates": sorted(rejected),
        "killed_families": sorted(killed_families),
        "cancelled_work": sorted(cancelled),
        "scheduled": sorted(scheduled),
        "open_frontier": open_frontier,
        "selected_action": selected,
        "trace": trace,
    }

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: flash_closure_v1.py evidence.json")
    out = close(load(sys.argv[1]))
    print(json.dumps(out, indent=2, sort_keys=True))
    print("FLASH_CLOSE_FIXED_POINT", file=sys.stderr)
    print("FLASH_SELECTED_ACTION="+out["selected_action"], file=sys.stderr)

if __name__ == "__main__":
    main()
