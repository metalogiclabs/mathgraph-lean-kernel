#!/usr/bin/env python3
"""Complete protected portable test and measured instruction comparison.

Identical pinned source and compilation on two arms; candidate only forwards
the existing parent support projection into App type inference.
Valgrind guest instructions are developmental proxy, never Arena PMU.
"""
import hashlib,json,math,pathlib,subprocess,sys
root=pathlib.Path(sys.argv[1]);output=pathlib.Path(sys.argv[2]);output.mkdir(parents=True,exist_ok=True)
exes={"base":"/tmp/flash-app-base-target/release/sokonanoda",
      "candidate":"/tmp/flash-app-candidate-target/release/sokonanoda"}
flags=["--stdin","--nat-extension","--string-extension","--axiom-allow-all","--threads","4"]
cases=[(g,p) for g in ("good","bad") for p in sorted((root/g).rglob("*.ndjson"))]
assert sum(g=="good" for g,_ in cases)==125
assert sum(g=="bad" for g,_ in cases)==71
rows=[]
for group,path in cases:
    verdict={}
    for arm,exe in exes.items():
        with path.open("rb") as f:
            proc=subprocess.run([exe,*flags],stdin=f,stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE,timeout=90)
        verdict[arm]=proc.returncode
        assert proc.returncode in (0,1,2),(path,arm,proc.returncode,proc.stderr[-500:])
        assert (proc.returncode==0) if group=="good" else (proc.returncode!=0),(path,arm,proc.returncode)
    assert verdict["base"]==verdict["candidate"],(path,verdict)
    rows.append({"case":str(path.relative_to(root)),"group":group,
                 "exit":verdict["base"],"sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
counts={str(k):sum(row["exit"]==k for row in rows) for k in (0,1,2)}
assert counts=={"0":125,"1":69,"2":2},counts
(output/"verdicts.json").write_text(json.dumps({"counts":counts,"cases":rows},indent=2)+"\n")
print("FLASH_APP_PROTECTED="+json.dumps(counts),flush=True)
focus=("init-prelude","perf/grind-ring-5","perf/magma-list-pair-n7",
       "perf/magma-list-deep-n21","perf/fueled-chain")
observations=[]
for i,case in enumerate(focus):
    file=root/"good"/(case+".ndjson")
    totals={}
    for arm in (("base","candidate") if i%2==0 else ("candidate","base")):
        fileout=output/(case.replace("/","_")+"-"+arm+".callgrind")
        with file.open("rb") as fd:
            result=subprocess.run(["valgrind","--tool=callgrind","--quiet",
               "--cache-sim=no","--branch-sim=no","--callgrind-out-file="+str(fileout),
               exes[arm],*flags],stdin=fd,stdout=subprocess.DEVNULL,
               stderr=subprocess.PIPE,timeout=700)
        assert result.returncode==0,(case,arm,result.returncode,result.stderr[-800:])
        guest=next((int(line.split()[1]) for line in fileout.read_text().splitlines()
                    if line.startswith("summary: ")),None)
        assert guest and guest>1000000,(case,arm,guest)
        totals[arm]=guest
        fileout.unlink()
    row={"case":case,"base_Ir":totals["base"],"candidate_Ir":totals["candidate"],
         "candidate_over_base":totals["candidate"]/totals["base"]}
    observations.append(row)
    print("FLASH_APP_CASE="+json.dumps(row),flush=True)
geo=math.exp(sum(math.log(x["candidate_over_base"]) for x in observations)/len(observations))
worst=max(x["candidate_over_base"] for x in observations)
decision=("NEXT_FULL_MATHLIB_AB" if geo<=0.99 and worst<=1.01
          else "NO_MATERIAL_FIVE_CASE_INSTRUCTION_GAIN")
report={"source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
        "base":"source + previously qualified sparse-prune and 4x-growth interventions",
        "candidate":"base + pass source-verified parent support env to infer_app_v",
        "scope":"single binder depth, application child support is subset of parent support",
        "portable_verdicts":counts,"guest_Ir_geomean":geo,"worst_case_ratio":worst,
        "observations":observations,"decision":decision,
        "full_mathlib_accept_qualified":False,"official_rank_qualified":False}
(output/"decision.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("FLASH_APP_DECISION="+json.dumps({"decision":decision,"geomean":geo,"worst":worst}),flush=True)
