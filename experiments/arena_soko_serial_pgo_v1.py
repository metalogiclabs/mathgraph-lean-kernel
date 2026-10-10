#!/usr/bin/env python3
"""A/B current sokonanoda, identical source/flags, differing ONLY in PGO training thread count."""
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys

root=Path(sys.argv[1]); output=Path(sys.argv[2]); output.mkdir(parents=True,exist_ok=True)
paths={"train4":"/tmp/soko-pgo-4t","train1":"/tmp/soko-pgo-1t"}
opt=["--stdin","--nat-extension","--string-extension","--axiom-allow-all","--threads","1"]
cases=[("good",p) for p in sorted((root/"good").rglob("*.ndjson"))]+[
    ("bad",p) for p in sorted((root/"bad").rglob("*.ndjson"))]
assert sum(bucket=="good" for bucket,_ in cases)==125
assert sum(bucket=="bad" for bucket,_ in cases)==71
verdicts=[]
for bucket,path in cases:
    data=path.read_bytes()
    results={}
    for name,binary in paths.items():
        p=subprocess.run([binary,*opt],input=data,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=90)
        results[name]=p.returncode
    assert results["train4"]==results["train1"],(path,results)
    assert results["train1"] in (0,1,2), (path,results)
    assert (results["train1"]==0) if bucket=="good" else (results["train1"]!=0), (path,results)
    verdicts.append({"case":str(path.relative_to(root)),"verdict":results["train1"]})
print("MSI_SOKO_PGO_196="+json.dumps({
    "cases":196,"valid_accepted":sum(x["verdict"]==0 for x in verdicts),
    "invalid_declined":sum(x["verdict"]==2 for x in verdicts),
    "all_equal":True
}),flush=True)

focus=["init-prelude","perf/grind-ring-5","perf/magma-list-pair-n7",
        "perf/magma-list-deep-n21","perf/fueled-chain"]
measured=[]
for case in focus:
    file=root/"good"/(case+".ndjson")
    result={}
    for arm,exe in paths.items():
        artifact=output/(case.replace("/","_")+"-"+arm+".callgrind")
        with file.open("rb") as fi:
            p=subprocess.run(["valgrind","--tool=callgrind","--quiet",
                "--collect-jumps=no","--callgrind-out-file="+str(artifact),exe,*opt],
                stdin=fi,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=300)
        assert p.returncode==0,(arm,case,p.stderr[-500:])
        total=None
        for line in artifact.read_text().splitlines():
            if line.startswith("summary: "):
                total=int(line.split()[1])
                break
        assert total and total>1_000_000,(case,arm,total)
        result[arm]=total
        artifact.unlink()
    ratio=result["train1"]/result["train4"]
    record={"case":case,"Ir_pgo4":result["train4"],
           "Ir_pgo1":result["train1"],"ratio_one_over_four":ratio}
    measured.append(record)
    print("MSI_SOKO_PGO_IR="+json.dumps(record),flush=True)
geo=math.exp(sum(math.log(x["ratio_one_over_four"]) for x in measured)/len(measured))
decision="GO_MATHLIB" if geo<=0.995 and max(x["ratio_one_over_four"] for x in measured)<=1.01 else "NO_MATERIAL_PORTABLE_GAIN"
summary={"base_sha":"7645b1e1fcacfe410c99141f1234381d995b325d",
    "candidate_sha":os.environ["GITHUB_SHA"],
    "difference":"PGO training is one versus four threads, identical source/binary flags",
    "scope":"portable 125+71; deterministic Callgrind guest Ir is NOT Arena hardware retired instructions",
    "geometric_ratio":geo,"decision":decision,"cases":measured,"verdicts":verdicts}
(output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
print("MSI_SOKO_PGO_DECISION="+json.dumps({"decision":decision,"geo_ratio":geo}),flush=True)
