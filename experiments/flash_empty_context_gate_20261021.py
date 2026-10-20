#!/usr/bin/env python3
"""Measure exact pinned Arena cases and Callgrind costs for two research variants."""
import hashlib, json, math, pathlib, subprocess, sys
root=pathlib.Path(sys.argv[1]); output=pathlib.Path(sys.argv[2])
output.mkdir(parents=True,exist_ok=True)
executables={"base":"/tmp/flash-empty-base-target/release/sokonanoda",
             "candidate":"/tmp/flash-empty-candidate-target/release/sokonanoda"}
args=["--stdin","--nat-extension","--string-extension","--axiom-allow-all","--threads","4"]
cases=[(kind,p) for kind in ("good","bad") for p in sorted((root/kind).rglob("*.ndjson"))]
assert len(cases)==196
rows=[]
for kind,path in cases:
    outcomes={}
    for arm,exe in executables.items():
        with path.open("rb") as f:
            result=subprocess.run([exe,*args],stdin=f,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=90)
        outcomes[arm]=result.returncode
    assert outcomes["base"]==outcomes["candidate"]
    assert outcomes["base"] in (0,1,2)
    assert (outcomes["base"]==0) if kind=="good" else (outcomes["base"]!=0)
    rows.append({"case":str(path.relative_to(root)),"group":kind,"exit":outcomes["base"],"sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
counts={str(k):sum(r["exit"]==k for r in rows) for k in (0,1,2)}
assert counts=={"0":125,"1":69,"2":2},counts
(output/"protected.json").write_text(json.dumps({"counts":counts,"rows":rows},indent=2))
print("PROTECTED="+json.dumps(counts),flush=True)
focus=["init-prelude","perf/grind-ring-5","perf/magma-list-pair-n7","perf/magma-list-deep-n21","perf/fueled-chain"]
measured=[]
for case in focus:
    pair={}
    for arm,exe in executables.items():
        dest=output/(case.replace("/","_")+"-"+arm+".callgrind")
        with (root/"good"/(case+".ndjson")).open("rb") as f:
            result=subprocess.run(["valgrind","--tool=callgrind","--quiet","--callgrind-out-file="+str(dest),exe,*args],stdin=f,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=600)
        assert result.returncode==0,(case,arm,result.returncode)
        pair[arm]=int(next(x.split()[1] for x in dest.read_text().splitlines() if x.startswith("summary: ")))
        dest.unlink()
    measured.append({"case":case,**pair,"ratio":pair["candidate"]/pair["base"]})
    print("MEASURE="+json.dumps(measured[-1]),flush=True)
ratio=math.exp(sum(math.log(r["ratio"]) for r in measured)/len(measured))
decision="CANDIDATE" if ratio<=0.99 and max(r["ratio"] for r in measured)<=1.01 else "NO_GAIN"
(output/"decision.json").write_text(json.dumps({"ratio":ratio,"decision":decision,"rows":measured},indent=2))
print("DECISION="+json.dumps({"decision":decision,"ratio":ratio}),flush=True)
