#!/usr/bin/env python3
"""Protect a minimal goal-directed Pi/lambda check under exact original Soko.

All 196 original portable verdicts are compared twice: baseline vs fast,
and baseline vs candidate with *original check shadow* enabled for every
successful fast judgment. Only then measure Callgrind guest Ir and native RSS.
This does not promote an unverified rewrite or measure official PMU score.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

root = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
paths = {"baseline":"/tmp/soko-goal-chain-baseline.bin",
         "candidate":"/tmp/soko-goal-chain-candidate.bin"}
opts = ["--stdin", "--nat-extension", "--string-extension",
        "--axiom-allow-all", "--threads", "4"]
positive = sorted((root/"good").rglob("*.ndjson"))
negative = sorted((root/"bad").rglob("*.ndjson"))
assert (len(positive),len(negative))==(125,71),(len(positive),len(negative))

def run(path, arm, shadow=False):
    env=dict(os.environ)
    env.pop("MG_PI_CHECK_SHADOW",None)
    env.pop("MG_PI_REPORT",None)
    if arm=="candidate":
        env["MG_PI_REPORT"]="1"
        if shadow:env["MG_PI_CHECK_SHADOW"]="1"
    with path.open("rb") as fin:
        p=subprocess.run([paths[arm],*opts],stdin=fin,stdout=subprocess.DEVNULL,
                         stderr=subprocess.PIPE,env=env,timeout=240)
    stderr=p.stderr.decode(errors="replace")
    count=None
    if arm=="candidate":
        m=re.findall(r"^MG_PI_GOAL_APPLIED=(\d+)$",stderr,re.M)
        # A parser/structural-admission rejection can finish before
        # check_all_declars prints any diagnostic count.
        if len(m)==1:
            count=int(m[0])
        else:
            assert not m and p.returncode in (1,2), ("missing pi count on checked input",str(path),stderr[-500:])
            count=0
    return {"returncode":p.returncode,"pi_goals":count,
            "error_tail":stderr[-850:] if p.returncode else ""}

rows=[];applied_regular=applied_shadow=0
for bucket, inputs in (("good",positive),("bad",negative)):
    for path in inputs:
        first=run(path,"baseline")
        candidate=run(path,"candidate")
        shadow=run(path,"candidate",shadow=True)
        codes=(first["returncode"],candidate["returncode"],shadow["returncode"])
        assert len(set(codes))==1,("EXPECTED_PI_VERDICT_MISMATCH",str(path),codes,first,candidate,shadow)
        rc=first["returncode"]
        assert rc==0 if bucket=="good" else rc in (1,2),("PROTECTED_INVALID_OR_VALID_REGRESSION",str(path),codes)
        applied_regular+=candidate["pi_goals"]
        applied_shadow+=shadow["pi_goals"]
        rows.append({"input":str(path.relative_to(root)),"verdict":rc,
                     "candidate_pi_goals":candidate["pi_goals"],
                     "shadow_pi_goals":shadow["pi_goals"]})
assert applied_regular==applied_shadow,("SHADOW_JUDGMENT_COUNT_CHANGED",applied_regular,applied_shadow)
counts={"accepted":sum(r["verdict"]==0 for r in rows),
        "rejected":sum(r["verdict"]==1 for r in rows),
        "declined":sum(r["verdict"]==2 for r in rows)}
assert counts=={"accepted":125,"rejected":69,"declined":2},counts
print("GOAL_PI_VERDICTS="+json.dumps({"total":len(rows),**counts,
    "wrong":0,"baseline_fast_shadow_identical":True,
    "candidate_goals":applied_regular,"shadow_goals":applied_shadow}),flush=True)

cases = ["init-prelude","perf/grind-ring-5","perf/magma-list-deep-n21",
         "perf/magma-list-pair-n7","perf/fueled-chain"]
records=[]
for case in cases:
    path = root/"good"/(case+".ndjson")
    assert path.is_file(),path
    row={"case":case,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    for arm,binary in paths.items():
        rss = out / (case.replace("/","_") + "-" + arm + ".rss")
        env=dict(os.environ)
        env.pop("MG_PI_CHECK_SHADOW",None)
        env.pop("MG_PI_REPORT",None)
        if arm=="candidate":env["MG_PI_REPORT"]="1"
        with path.open("rb") as fin:
            p=subprocess.run(["/usr/bin/time","-f","%M","-o",str(rss),
                binary,*opts],stdin=fin,stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,timeout=480,env=env)
        assert p.returncode==0,(case,arm,"native",p.returncode,p.stderr[-500:])
        row[arm+"_rss_kb"]=int(rss.read_text().strip())
        if arm=="candidate":
            m=re.findall(rb"^MG_PI_GOAL_APPLIED=(\d+)$",p.stderr,re.M)
            assert len(m)==1,(case,"missing candidate count")
            row["pi_goals_eligible"]=int(m[0])
        rss.unlink()
        profile=out/(case.replace("/","_")+"-"+arm+".callgrind")
        with path.open("rb") as fin:
            p=subprocess.run(["valgrind","--tool=callgrind","--cache-sim=no",
                "--branch-sim=no","--callgrind-out-file="+str(profile),
                binary,*opts],stdin=fin,stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,timeout=1000,env=env)
        assert p.returncode==0,(case,arm,"callgrind",p.returncode,p.stderr[-900:])
        m=re.search(r"^summary:\s*(\d+)\s*$",profile.read_text(),re.M)
        assert m,(case,arm,"callgrind Ir absent")
        row[arm+"_guest_Ir"]=int(m.group(1))
        profile.unlink()
    row["candidate_over_baseline_guest_Ir"] = row["candidate_guest_Ir"]/row["baseline_guest_Ir"]
    row["candidate_over_baseline_rss"] = row["candidate_rss_kb"]/max(1,row["baseline_rss_kb"])
    records.append(row)
    print("GOAL_PI_CASE="+json.dumps(row),flush=True)

ratio=math.exp(sum(math.log(x["candidate_over_baseline_guest_Ir"]) for x in records)/len(records))
rss=max(x["candidate_over_baseline_rss"] for x in records)
worst=max(x["candidate_over_baseline_guest_Ir"] for x in records)
decision=("PROCEED_TO_PINNED_FULL_MATHLIB" if (
    ratio<=0.99 and worst<=1.025 and rss<=1.10 and applied_regular>0)
    else "NO_MATERIAL_GOAL_PI_PROXY_GAIN")
report={"authority":"development-only recursive dependent Lambda/Pi goal-judgment decomposition with checked dependent body",
        "upstream_source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
        "common_parent":"exact sparse touched-slot reset plus 4x PtrMap growth",
        "branch_commit":os.environ.get("GITHUB_SHA"),
        "no_new_axioms_or_type_rules":True,
        "negative_controls":{"portable196":counts,"no_wrong":True,
                             "shadow_original_checks_each_candidate_fast_judgment":True},
        "portable196":rows,"goal_pi_applied_in_corpus":applied_regular,
        "cases":records,"guest_Ir_ratio":ratio,"max_guest_Ir_ratio":worst,
        "max_native_rss_ratio":rss,"decision":decision,
        "instruction_meter":"Callgrind guest Ir, not hardware PMU retired instructions",
        "official_rank_qualified":False,"full_mathlib_warrant":False}
(out/"report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("GOAL_PI_SUMMARY="+json.dumps({"ratio":ratio,"max_rss_ratio":rss,
    "candidate_checked_pi_count":applied_regular,"decision":decision,
    "official_rank_qualified":False}),flush=True)
