#!/usr/bin/env python3
import itertools, json, math, re, sys
from collections import defaultdict
from pathlib import Path

RE = re.compile(
    r"V117_CELL k=(\S+) root=(\S+) mask=(\S+) var_mass=(\S+) depth=(\S+) app_spine=(\S+) "
    r"calls=(\d+) hits=(\d+) success=(\d+) fail=(\d+) selected_sum=(\d+) saved_sum=(\d+) same_env=(\d+)"
)
BASE = ("k","root","mask")
NEW = ("var_mass","depth","app_spine")

def parse(workload, path):
    rows=[]
    for line in Path(path).read_text(errors="replace").splitlines():
        m=RE.search(line)
        if not m: continue
        k,root,mask,var_mass,depth,app_spine,*nums=m.groups()
        calls,hits,success,fail,selected,saved,same=map(int,nums)
        rows.append(dict(
            workload=workload,k=k,root=root,mask=mask,var_mass=var_mass,depth=depth,app_spine=app_spine,
            calls=calls,hits=hits,success=success,fail=fail,selected_sum=selected,saved_sum=saved,same_env=same
        ))
    return rows

def outcome(r, name):
    s=max(1,r["success"])
    if name=="saved":
        return r["saved_sum"]/s
    if name=="selected":
        return r["selected_sum"]/s
    if name=="yield":
        return r["saved_sum"]/max(1,r["selected_sum"])
    raise KeyError(name)

def score(rows, extra, outcome_name):
    features=BASE+tuple(extra)
    groups=defaultdict(list)
    for r in rows:
        if r["success"] == 0:
            continue
        groups[tuple(r[f] for f in features)].append(r)
    sse=0.0
    weight=0.0
    for rs in groups.values():
        ws=[r["success"] for r in rs]
        ys=[outcome(r,outcome_name) for r in rs]
        w=sum(ws)
        if w==0: continue
        mu=sum(a*b for a,b in zip(ws,ys))/w
        sse += sum(a*(b-mu)**2 for a,b in zip(ws,ys))
        weight += w
    rmse=math.sqrt(sse/max(1.0,weight))
    return dict(features=list(features),extra=list(extra),cost=len(extra),cells=len(groups),sse=sse,weight=weight,rmse=rmse)

def main():
    if len(sys.argv) < 4:
        raise SystemExit("usage: analyze_boundary_v117.py REPORT.json workload=file ...")
    report_path=Path(sys.argv[1])
    rows=[]
    for spec in sys.argv[2:]:
        workload,path=spec.split("=",1)
        rows.extend(parse(workload,path))
    if not rows:
        raise SystemExit("V117: no atlas rows")

    all_scores={}
    for out in ("saved","selected","yield"):
        scores=[]
        for n in range(len(NEW)+1):
            for extra in itertools.combinations(NEW,n):
                scores.append(score(rows,extra,out))
        baseline=next(x for x in scores if x["cost"]==0)
        for x in scores:
            x["rmse_reduction_vs_base"] = 0.0 if baseline["rmse"]==0 else 1.0-x["rmse"]/baseline["rmse"]
        all_scores[out]=scores

    result={
        "authority":{
            "fixed_features":list(BASE),
            "candidate_construction_time_features":list(NEW),
            "selection":"exhaustive subset search; no workload identity is available to the predictor",
            "outcomes":[
                "environment positions saved per successful wide projection",
                "selected dependency count per successful wide projection",
                "saved/selected structural yield"
            ],
        },
        "workloads":sorted({r["workload"] for r in rows}),
        "rows":len(rows),
        "scores":all_scores,
    }
    report_path.write_text(json.dumps(result,indent=2,sort_keys=True))

    print("V117_ANALYSIS_BEGIN")
    for out,scores in all_scores.items():
        baseline=next(x for x in scores if x["cost"]==0)
        print(f"V117_BASE outcome={out} rmse={baseline['rmse']:.6f} cells={baseline['cells']}")
        for cost in range(1,len(NEW)+1):
            xs=[x for x in scores if x["cost"]==cost]
            best=min(xs,key=lambda x:(x["rmse"],x["extra"]))
            print(
                f"V117_BEST outcome={out} cost={cost} features={','.join(best['extra'])} "
                f"rmse={best['rmse']:.6f} reduction={best['rmse_reduction_vs_base']:.6f} cells={best['cells']}"
            )
    print("V117_ANALYSIS_END")
    print("V117_ANALYSIS_COMPLETE=PASS")

if __name__=="__main__":
    main()
