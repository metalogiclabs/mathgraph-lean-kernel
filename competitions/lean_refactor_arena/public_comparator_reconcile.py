#!/usr/bin/env python3
"""Reconcile a 15-row local warm-up portfolio against public comparator trials.

This does not promote external trials to MathGraph verification. It proves exact
candidate identity and carries forward the public run's reported measurements as
an explicitly external score floor while local/public-harness requalification runs.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

def slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")

def rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--portfolio",required=True)
    ap.add_argument("--public-trials",required=True)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()

    portfolio=rows(Path(args.portfolio))
    if len(portfolio)!=15 or len({r["name"] for r in portfolio})!=15:
        raise SystemExit("portfolio must contain exactly 15 unique targets")

    reconciled=[]
    for local in portfolio:
        name=local["name"]
        trial=Path(args.public_trials)/f"{slug(name)}.jsonl"
        if not trial.is_file():
            raise SystemExit(f"missing public trial file: {trial}")
        valid=[
            r for r in rows(trial)
            if r.get("name")==name
            and r.get("compiled") is True
            and float(r.get("survival_pct") or 0)>=100.0
            and isinstance(r.get("objective_sum_pct"),(int,float))
            and isinstance(r.get("candidate"),str)
        ]
        if not valid:
            raise SystemExit(f"no valid public comparator trial for {name}")
        best=max(valid,key=lambda r:float(r["objective_sum_pct"]))
        exact=local["proof"].strip()==best["candidate"].strip()
        reconciled.append({
            "name":name,
            "exact_candidate_match":exact,
            "local_label":local.get("label"),
            "local_provenance":local.get("provenance"),
            "public_hash":best.get("hash"),
            "public_objective_sum_pct":best.get("objective_sum_pct"),
            "public_combined_pct":best.get("combined_pct"),
            "public_length":best.get("length"),
            "public_heartbeats":best.get("heartbeats"),
            "public_survival_pct":best.get("survival_pct"),
            "public_wrapper":best.get("wrapper"),
            "public_episode":best.get("episode"),
        })

    exact=[r for r in reconciled if r["exact_candidate_match"]]
    external_obj=sum(float(r["public_objective_sum_pct"]) for r in exact)
    report={
        "schema":"mathgraph.lean-refactor-arena.external-reconciliation.v1",
        "status":"EXTERNAL_EVIDENCE_ONLY",
        "portfolio_count":len(portfolio),
        "exact_public_best_matches":len(exact),
        "all_exact":len(exact)==len(portfolio),
        "external_objective_sum_total_for_exact_matches":round(external_obj,2),
        "external_objective_sum_mean_for_exact_matches":round(external_obj/len(exact),2) if exact else None,
        "external_combined_mean_if_full_survival":round((external_obj/len(exact)+100.0)/3.0,2) if exact else None,
        "boundary":"Metrics are copied only from exact-matching public competitor trial rows. They are not MathGraph verifier results and do not establish official leaderboard rank.",
        "rows":reconciled,
    }
    Path(args.out).write_text(json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="rows"},indent=2))
    for r in reconciled:
        print(f"{'MATCH' if r['exact_candidate_match'] else 'DIFF'} {r['name']} public_obj={r['public_objective_sum_pct']}")
    if not report["all_exact"]:
        raise SystemExit("PORTFOLIO_DIFFERS_FROM_PUBLIC_BEST_ON_SOME_TARGETS")
    print("VERIFIED_EXACT_PUBLIC_COMPARATOR_PORTFOLIO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
