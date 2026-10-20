#!/usr/bin/env python3
"""Four-arm source-factorial gate for duplicated context projection.

Each arm checks original Lean Arena frozen portable 125 good / 71 bad.
All five Callgrind counts include parsing, checking, allocations and runtime.
Callgrind guest Ir is NOT official Arena hardware retired instructions.
"""
import hashlib
import json
import math
import os
import pathlib
import subprocess
import sys

root, output = (pathlib.Path(x) for x in sys.argv[1:3])
output.mkdir(parents=True, exist_ok=True)
arms=("base","infer","eval","both")
executables={name:pathlib.Path("/tmp/flash-fused-"+name+"-target/release/sokonanoda") for name in arms}
flags=["--stdin","--nat-extension","--string-extension","--axiom-allow-all","--threads","4"]
for name,path in executables.items():
    assert path.is_file(),(name,path)

cases=[(kind,p) for kind in ("good","bad") for p in sorted((root/kind).rglob("*.ndjson"))]
assert sum(k=="good" for k,_ in cases)==125
assert sum(k=="bad" for k,_ in cases)==71
judgments=[]
for kind,file in cases:
    row={"case":str(file.relative_to(root)), "kind":kind,
         "sha256":hashlib.sha256(file.read_bytes()).hexdigest()}
    for name,exe in executables.items():
        with file.open("rb") as f:
            run=subprocess.run([str(exe),*flags],stdin=f,stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE,timeout=90)
        row[name]=run.returncode
        assert run.returncode in (0,1,2),(row,run.stderr[-400:])
        assert (run.returncode==0) if kind=="good" else (run.returncode!=0),row
    assert len({row[name] for name in arms})==1,row
    judgments.append(row)
counts={str(n):sum(r["base"]==n for r in judgments) for n in (0,1,2)}
assert counts=={"0":125,"1":69,"2":2},counts
(output/"protected196.json").write_text(json.dumps({"counts":counts,"rows":judgments},indent=2)+"\n")
print("FLASH_FUSED_PROTECTED="+json.dumps(counts),flush=True)

workloads=("init-prelude","perf/grind-ring-5","perf/magma-list-pair-n7",
           "perf/magma-list-deep-n21","perf/fueled-chain")
rows=[]
for k,test in enumerate(workloads):
    file=root/"good"/(test+".ndjson")
    assert file.is_file(),file
    outcomes={}
    order=arms[k%len(arms):]+arms[:k%len(arms)]
    for arm in order:
        outfile=output/(test.replace("/","_")+"-"+arm+".callgrind")
        command=["valgrind","--tool=callgrind","--quiet","--cache-sim=no",
                 "--branch-sim=no","--callgrind-out-file="+str(outfile),
                 str(executables[arm]),*flags]
        with file.open("rb") as src:
            proc=subprocess.run(command,stdin=src,stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE,timeout=650)
        assert proc.returncode==0,(test,arm,proc.returncode,proc.stderr[-800:])
        total=next((int(line.split()[1]) for line in outfile.read_text().splitlines()
                    if line.startswith("summary: ")),None)
        assert total is not None and total>1000000,(test,arm,total)
        outcomes[arm]=total
        outfile.unlink()
    ratios={arm:outcomes[arm]/outcomes["base"] for arm in arms if arm!="base"}
    row={"test":test,"instructions":outcomes,"ratios":ratios}
    rows.append(row)
    print("FLASH_FUSED_CASE="+json.dumps(row),flush=True)

geo={arm:math.exp(sum(math.log(r["ratios"][arm]) for r in rows)/len(rows))
     for arm in arms if arm!="base"}
worst={arm:max(r["ratios"][arm] for r in rows) for arm in geo}
# Mathematically verified parity is necessary but does not by itself
# authorize promotion on full Mathlib. Require >=1% material saving.
eligible=[name for name in geo if geo[name]<=0.99 and worst[name]<=1.01]
winning=min(eligible,key=lambda k:geo[k]) if eligible else None
report={"frozen_source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
        "common_patch":"qualified sparse PruneMemo exact reset + 4x PtrMap growth",
        "interventions":"reuse one exact source-keyed relevant environment for Lambda inference and for open Lambda/Pi evaluation",
        "checksum_manifest":{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in executables.items()},
        "protected196":counts,"cases":rows,"geomean":geo,"worst_ratio":worst,
        "eligible_for_full_mathlib":winning,
        "decision":"NEXT_FULL_MATHLIB_GUEST_IR" if winning else "NO_MATERIAL_PORTABLE_INSTRUCTION_SAVING",
        "verified_full_mathlib":False,"official_rank_qualified":False,
        "measurement":"Whole-process portable Callgrind guest Ir, not native PMU"}
(output/"decision.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("FLASH_FUSED_DECISION="+json.dumps({"decision":report["decision"],"geomean":geo,
        "worst":worst,"winner":winning}),flush=True)
