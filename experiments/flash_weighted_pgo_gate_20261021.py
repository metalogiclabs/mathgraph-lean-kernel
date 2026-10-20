#!/usr/bin/env python3
"""Prospective PGO blend comparison for one identical source-controlled Flash kernel.

Only compiler profile weights differ. Measure complete process instruction
proxies on the same frozen portable Arena source, and fail closed on verdict
changes. This does not establish the official Arena retired-instruction score.
"""
import hashlib
import json
import math
import pathlib
import subprocess
import sys

cases_root=pathlib.Path(sys.argv[1])
out=pathlib.Path(sys.argv[2]); out.mkdir(parents=True,exist_ok=True)
names=("init","mix10","mix100","mix1000")
binaries={n:pathlib.Path("/tmp/flash-weighted-binary-"+n) for n in names}
flags=["--stdin","--nat-extension","--string-extension",
       "--axiom-allow-all","--threads","4"]
for k,exe in binaries.items():
    assert exe.is_file(),(k,exe)
    print("FLASH_WEIGHTED_BINARY="+json.dumps({"name":k,
       "sha256":hashlib.sha256(exe.read_bytes()).hexdigest()}),flush=True)

cases=[(part,f) for part in ("good","bad") for f in sorted((cases_root/part).rglob("*.ndjson"))]
assert sum(part=="good" for part,_ in cases)==125
assert sum(part=="bad" for part,_ in cases)==71
verdicts=[]
for part,src in cases:
    row={"case":str(src.relative_to(cases_root)),"group":part,
         "sha256":hashlib.sha256(src.read_bytes()).hexdigest()}
    for name,exe in binaries.items():
        with src.open("rb") as f:
            got=subprocess.run([str(exe),*flags],stdin=f,stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE,timeout=100)
        row[name]=got.returncode
        assert got.returncode in (0,1,2),(row,got.stderr[-400:])
        assert (got.returncode==0) if part=="good" else (got.returncode!=0),row
    assert len({row[k] for k in names})==1,row
    verdicts.append(row)
counts={str(i):sum(v["init"]==i for v in verdicts) for i in (0,1,2)}
assert counts=={"0":125,"1":69,"2":2},counts
(out/"protected196.json").write_text(json.dumps({"counts":counts,"rows":verdicts},indent=2)+"\n")
print("FLASH_WEIGHTED_PROTECTED="+json.dumps(counts),flush=True)

focus=("init-prelude","perf/grind-ring-5","perf/magma-list-pair-n7",
       "perf/magma-list-deep-n21","perf/fueled-chain")
measured=[]
for i,case in enumerate(focus):
    src=cases_root/"good"/(case+".ndjson")
    assert src.is_file(),src
    outcomes={}
    # Rotate execution order to avoid over-crediting first-run cache warmth.
    order=names[i%len(names):]+names[:i%len(names)]
    for name in order:
        outfile=out/(case.replace("/","_")+"-"+name+".callgrind")
        with src.open("rb") as f:
            got=subprocess.run(["valgrind","--tool=callgrind","--quiet",
                "--cache-sim=no","--branch-sim=no","--callgrind-out-file="+str(outfile),
                str(binaries[name]),*flags],stdin=f,stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,timeout=900)
        assert got.returncode==0,(case,name,got.returncode,got.stderr[-400:])
        result=next((int(line.split()[1]) for line in outfile.read_text().splitlines()
                     if line.startswith("summary: ")),None)
        assert result and result>1000000,(case,name,result)
        outcomes[name]=result
        outfile.unlink()
    row={"test":case,"guest_ir":outcomes,
         "ratios":{n:outcomes[n]/outcomes["init"] for n in names[1:]}}
    measured.append(row)
    print("FLASH_WEIGHTED_CASE="+json.dumps(row),flush=True)

geomean={name:math.exp(sum(math.log(row["ratios"][name]) for row in measured)/len(measured))
         for name in names[1:]}
worst={name:max(row["ratios"][name] for row in measured) for name in names[1:]}
qualified=[n for n in names[1:] if geomean[n] <= 0.995 and worst[n] <= 1.01]
best=min(qualified,key=lambda x:geomean[x]) if qualified else None
report={"source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
        "source_patches":"qualified sparse exact reset plus 4x growth, identical for all arms",
        "profiles":"init alone or llvm-profdata merged indexed profiles with Init:Mathlib weights of 10:1, 100:1, 1000:1",
        "metric":"Valgrind whole-process guest Ir, NOT hardware retired instructions",
        "protected196":counts,"geomean":geomean,"largest_regression":worst,
        "winning_candidate":best,"decision":"GO_FULL_MATHLIB" if best else "NO_MATERIAL_FIVE_CASE_INSTRUCTION_GAIN",
        "cases":measured,"official_rank_qualified":False}
(out/"decision.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("FLASH_WEIGHTED_DECISION="+json.dumps({"decision":report["decision"],
      "geomean":geomean,"worst":worst,"candidate":best}),flush=True)
