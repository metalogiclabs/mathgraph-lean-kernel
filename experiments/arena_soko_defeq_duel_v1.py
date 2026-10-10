#!/usr/bin/env python3
"""Verify exact Soko checker verdict parity and Callgrind guest-instruction effect."""
import json,os,pathlib,re,subprocess,sys

root=pathlib.Path(sys.argv[1])
dest=pathlib.Path(sys.argv[2]);dest.mkdir(parents=True,exist_ok=True)
arms={"baseline":"/tmp/soko-defeq-original","candidate":"/tmp/soko-defeq-patched"}
cmd=["--stdin","--nat-extension","--string-extension","--axiom-allow-all","--threads","1"]
good=sorted((root/"good").rglob("*.ndjson"))
bad=sorted((root/"bad").rglob("*.ndjson"))
assert len(good)==125 and len(bad)==71,(len(good),len(bad))
results=[]
for bucket,files in (("good",good),("bad",bad)):
    for p in files:
        payload=p.read_bytes()
        rc={arm:subprocess.run([bin,*cmd],input=payload,
           stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=80).returncode
           for arm,bin in arms.items()}
        assert rc["baseline"]==rc["candidate"],(str(p),rc)
        if bucket=="good": assert rc["candidate"]==0,(str(p),rc)
        elif rc["candidate"]==0: raise AssertionError((str(p),rc))
        results.append({"case":str(p.relative_to(root)),"rc":rc["candidate"]})
print("SOKO_DEF_EQ_VERDICTS="+json.dumps({"total":len(results),"same":True,
  "accepted":sum(x["rc"]==0 for x in results),
  "rejected":sum(x["rc"]==1 for x in results),
  "declined":sum(x["rc"]==2 for x in results)}),flush=True)
case_names=["perf/grind-ring-5","perf/magma-list-deep-n21",
            "perf/magma-list-pair-n7","perf/fueled-chain"]
census=[]
for case in case_names:
    data=root/"good"/(case+".ndjson")
    row={"case":case}
    for name,binary in arms.items():
        profile=dest/(case.replace("/","_")+"-"+name+".callgrind")
        with data.open("rb") as stream:
            p=subprocess.run(["valgrind","--tool=callgrind","--cache-sim=no",
                "--branch-sim=no","--callgrind-out-file="+str(profile),
                binary,*cmd],stdin=stream,stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,timeout=360)
        assert p.returncode==0,(case,name,p.returncode,p.stderr[-350:])
        match=re.search(r"^summary:\s*(\d+)\s*$",profile.read_text(),re.M)
        assert match,profile
        row[name+"_Ir"]=int(match.group(1))
    row["speedup"]=row["baseline_Ir"]/row["candidate_Ir"]
    census.append(row)
    print("SOKO_DEF_EQ_IR="+json.dumps(row),flush=True)
(dest/"summary.json").write_text(json.dumps({
  "source":"7645b1e1fcacfe410c99141f1234381d995b325d",
  "new_source":os.environ["GITHUB_SHA"],
  "metric":"Valgrind Callgrind guest Ir; not Arena hardware retired instructions",
  "cases":census,"verdicts":results},indent=2)+"\n")
