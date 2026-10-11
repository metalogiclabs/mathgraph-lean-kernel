#!/usr/bin/env python3
"""Source-pinned 2x2 causal interaction gate; Callgrind guest Ir != Arena PMU.
A: exact sparse touched-slot clear; B: size and shift 1024->4096.
Neither patch changes the inference, conversion or Lean proof rules.
"""
import hashlib,json,math,os,pathlib,re,subprocess,sys

root=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
names=("baseline","sparse","wide","wide_sparse")
bins={n:"/tmp/soko-prune-factorial-"+n+".bin" for n in names}
args=["--stdin","--nat-extension","--string-extension","--axiom-allow-all","--threads","1"]
good=sorted((root/"good").rglob("*.ndjson"))
bad=sorted((root/"bad").rglob("*.ndjson"))
assert len(good)==125 and len(bad)==71,(len(good),len(bad))
checks=[]
for bucket,paths in (("good",good),("bad",bad)):
    for path in paths:
        codes={}
        for arm in names:
            with path.open("rb") as fin:
                p=subprocess.run([bins[arm],*args],stdin=fin,
                      stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=100)
            codes[arm]=p.returncode
        assert len(set(codes.values()))==1,(str(path),codes)
        v=codes["baseline"]
        assert (v==0 if bucket=="good" else v in (1,2)),(str(path),v)
        checks.append({"file":str(path.relative_to(root)),"verdict":v})
print("PRUNE_FACTORIAL_VERDICTS="+json.dumps({"count":len(checks),
  "accepted":sum(c["verdict"]==0 for c in checks),
  "rejected":sum(c["verdict"]==1 for c in checks),
  "declined":sum(c["verdict"]==2 for c in checks),
  "same_all_four":True}),flush=True)
cases=["init-prelude","perf/grind-ring-5","perf/magma-list-deep-n21",
       "perf/magma-list-pair-n7","perf/fueled-chain"]
rows=[]
for case in cases:
    path=root/"good"/(case+".ndjson")
    assert path.is_file(),path
    record={"case":case}
    for arm in names:
        output=out/(case.replace("/","_")+"-"+arm+".callgrind")
        with path.open("rb") as fin:
            p=subprocess.run(["valgrind","--tool=callgrind",
               "--cache-sim=no","--branch-sim=no",
               "--callgrind-out-file="+str(output),bins[arm],*args],
               stdin=fin,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=480)
        assert p.returncode==0,(case,arm,p.returncode,p.stderr[-700:])
        m=re.search(r"^summary:\s*(\d+)\s*$",output.read_text(),re.M)
        assert m,(case,arm)
        record[arm+"_Ir"]=int(m.group(1))
        output.unlink()
    record["sparse_over_baseline"]=record["sparse_Ir"]/record["baseline_Ir"]
    record["wide_over_baseline"]=record["wide_Ir"]/record["baseline_Ir"]
    record["joint_over_baseline"]=record["wide_sparse_Ir"]/record["baseline_Ir"]
    record["joint_over_sparse"]=record["wide_sparse_Ir"]/record["sparse_Ir"]
    record["joint_over_wide"]=record["wide_sparse_Ir"]/record["wide_Ir"]
    # Log-interaction distinguishes true synergy from independent multiplicative effects.
    record["interaction_log"]=math.log(record["wide_sparse_Ir"]*record["baseline_Ir"]/
                                   (record["wide_Ir"]*record["sparse_Ir"]))
    rows.append(record)
    print("PRUNE_FACTORIAL_CASE="+json.dumps(record),flush=True)
geomeans={k:math.exp(sum(math.log(r[k]) for r in rows)/len(rows))
          for k in ("sparse_over_baseline","wide_over_baseline",
                    "joint_over_baseline","joint_over_sparse","joint_over_wide")}
mean_interaction_log=sum(r["interaction_log"] for r in rows)/len(rows)
decision=("JOINT_CANDIDATE_FOR_FULL_MATHLIB" if
          geomeans["joint_over_baseline"]<0.99 and
          geomeans["joint_over_sparse"]<0.99 else
          "NO_MATERIAL_JOINT_WIN")
result={"source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
 "experiment":os.environ.get("GITHUB_SHA"),"arms":list(names),
 "meter":"Callgrind guest Ir (NOT Arena PMU retired instructions)",
 "portable_verdicts":checks,"cases":rows,"geomeans":geomeans,
 "interaction_geomean":math.exp(mean_interaction_log),"decision":decision,
 "official_rank_qualified":False}
(out/"prune-factorial.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
print("PRUNE_FACTORIAL_SUMMARY="+json.dumps({"geomeans":geomeans,
 "interaction_geomean":math.exp(mean_interaction_log),"decision":decision}),flush=True)
