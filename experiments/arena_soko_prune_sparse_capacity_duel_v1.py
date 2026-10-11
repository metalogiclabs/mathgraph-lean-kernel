#!/usr/bin/env python3
"""Source-exact cache-capacity factorial conditional on sparse reset.

No proof rules change. Protected 196 verdicts and 5 Callgrind workloads
decide whether removing full-table reset cost makes capacity useful.
"""
import hashlib, json, math, os, pathlib, re, subprocess, sys
root=pathlib.Path(sys.argv[1])
out=pathlib.Path(sys.argv[2])
out.mkdir(parents=True,exist_ok=True)
arms=("baseline","prune4096","prune16384")
bins={n:"/tmp/soko-prune-sparse-"+n+".bin" for n in arms}
opts=["--stdin","--nat-extension","--string-extension","--axiom-allow-all","--threads","1"]
good=sorted((root/"good").rglob("*.ndjson"))
bad=sorted((root/"bad").rglob("*.ndjson"))
assert len(good)==125 and len(bad)==71,(len(good),len(bad))
verdicts=[]
for bucket,files in (("good",good),("bad",bad)):
    for p in files:
        codes={}
        for arm in arms:
            with p.open("rb") as fin:
                x=subprocess.run([bins[arm],*opts],stdin=fin,stdout=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE,timeout=150)
            codes[arm]=x.returncode
        assert len(set(codes.values()))==1,(str(p),codes)
        rc=codes["baseline"]
        assert (rc==0 if bucket=="good" else rc in (1,2)),(str(p),codes)
        verdicts.append({"file":str(p.relative_to(root)),"rc":rc})
counts={"accepted":sum(v["rc"]==0 for v in verdicts),
        "rejected":sum(v["rc"]==1 for v in verdicts),
        "declined":sum(v["rc"]==2 for v in verdicts)}
assert counts=={"accepted":125,"rejected":69,"declined":2},counts
print("PRUNE_SPARSE_VERDICTS="+json.dumps({"total":len(verdicts),**counts,
   "same_three_arms":True,"wrong":0}),flush=True)

cases=["init-prelude","perf/grind-ring-5","perf/magma-list-deep-n21",
       "perf/magma-list-pair-n7","perf/fueled-chain"]
rows=[]
for case in cases:
    p=root/"good"/(case+".ndjson")
    assert p.is_file(),p
    row={"case":case,"input_sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
    for arm in arms:
        rssfile=out/(case.replace("/","_")+"-"+arm+".rss")
        with p.open("rb") as fin:
            x=subprocess.run(["/usr/bin/time","-f","%M","-o",str(rssfile),
                bins[arm],*opts],stdin=fin,stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,timeout=480)
        assert x.returncode==0,(case,arm,"native",x.returncode)
        row[arm+"_rss_kb"]=int(rssfile.read_text().strip())
        rssfile.unlink()
        profile=out/(case.replace("/","_")+"-"+arm+".callgrind")
        cmd=["valgrind","--tool=callgrind","--cache-sim=no","--branch-sim=no",
             "--callgrind-out-file="+str(profile),bins[arm],*opts]
        with p.open("rb") as fin:
            x=subprocess.run(cmd,stdin=fin,stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE,timeout=720)
        assert x.returncode==0,(case,arm,"callgrind",x.returncode,x.stderr[-800:])
        m=re.search(r"^summary:\s*(\d+)\s*$",profile.read_text(),re.M)
        assert m,(case,arm,"missing Callgrind Ir")
        row[arm+"_Ir"]=int(m.group(1))
        profile.unlink()
    for arm in arms[1:]:
        row[arm+"_over_baseline_ir"]=row[arm+"_Ir"]/row["baseline_Ir"]
        row[arm+"_over_baseline_rss"]=row[arm+"_rss_kb"]/max(1,row["baseline_rss_kb"])
    print("PRUNE_SPARSE_CASE="+json.dumps(row),flush=True)
    rows.append(row)
decisions={}
for arm in arms[1:]:
    ratios=[r[arm+"_over_baseline_ir"] for r in rows]
    geomean=math.exp(sum(math.log(x) for x in ratios)/len(ratios))
    worst=max(ratios)
    rss=max(r[arm+"_over_baseline_rss"] for r in rows)
    decisions[arm]={"geomean_ir_ratio":geomean,"worst_case_ir_ratio":worst,
                     "max_native_rss_ratio":rss,
                     "promotable_for_full_mathlib":bool(geomean<=0.99 and
                         worst<=1.025 and rss<=1.10)}
winner=min(arms[1:],key=lambda a:decisions[a]["geomean_ir_ratio"])
decision=("TEST_ON_FULL_MATHLIB_"+winner if
          decisions[winner]["promotable_for_full_mathlib"] else
          "NO_PROTECTED_PROXY_WIN")
summary={"exact_source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
         "experiment_commit":os.getenv("GITHUB_SHA"),
         "common_parent":"touched-slot sparse reset plus exact PtrMap 4x growth",
         "intervention":"PRUNE_DM_LEN 1024 to 4096 or 16384; hash shift changes with table power",
         "metric":"Valgrind Callgrind full-process guest Ir; NOT Arena PMU retired instructions",
         "portable196":verdicts,"verdict_counts":counts,"cases":rows,
         "decisions":decisions,"decision":decision,
         "official_rank_qualified":False}
(out/"report.json").write_text(json.dumps(summary,indent=2)+"\n")
print("PRUNE_SPARSE_SUMMARY="+json.dumps({"decisions":decisions,
     "decision":decision,"official_rank_qualified":False}),flush=True)
