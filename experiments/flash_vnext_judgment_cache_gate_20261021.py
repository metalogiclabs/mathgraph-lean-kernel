#!/usr/bin/env python3
"""Causal A/B on source-pinned joint contextual judgment record vs original maps.

Run both from the same original Soko revision and qualified sparse+growth
baseline, require all 196 Arena portable outcomes exactly, and report all raw
full-process Callgrind guest instructions. Fail closed on regressions in
semantic outcomes. No small-case result is an official Arena PMU claim.
"""
import hashlib,json,math,pathlib,statistics,subprocess,sys

tests=pathlib.Path(sys.argv[1])
out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
arms=("base","unified")
exes={arm:pathlib.Path("/tmp/flash-vnext-"+arm+"-target/release/sokonanoda") for arm in arms}
flags=["--stdin","--nat-extension","--string-extension","--axiom-allow-all","--threads","4"]
cases=[(kind,p) for kind in ("good","bad") for p in sorted((tests/kind).rglob("*.ndjson"))]
assert sum(k=="good" for k,p in cases)==125
assert sum(k=="bad" for k,p in cases)==71
verdicts=[]
for kind,src in cases:
    row={"case":str(src.relative_to(tests)), "group":kind,
         "sha256":hashlib.sha256(src.read_bytes()).hexdigest()}
    for arm in arms:
        with src.open("rb") as data:
            run=subprocess.run([str(exes[arm]),*flags],stdin=data,
                stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=120)
        row[arm]=run.returncode
        assert run.returncode in (0,1,2),(row,run.stderr[-500:])
        assert (run.returncode==0) if kind=="good" else (run.returncode!=0),row
    assert row["base"]==row["unified"],row
    verdicts.append(row)
counts={str(i):sum(x["base"]==i for x in verdicts) for i in (0,1,2)}
assert counts=={"0":125,"1":69,"2":2},counts
(out/"protected196.json").write_text(json.dumps({"counts":counts,"rows":verdicts},indent=2)+"\n")
print("FLASH_VNEXT_PROTECTED="+json.dumps(counts),flush=True)

workloads=("init-prelude","perf/grind-ring-5","perf/magma-list-pair-n7",
           "perf/magma-list-deep-n21","perf/fueled-chain")
results=[]
for i,case in enumerate(workloads):
    path=tests/"good"/(case+".ndjson")
    assert path.is_file(),path
    data={arm:[] for arm in arms}
    for rep in range(3):
        order=arms if (i+rep)%2==0 else tuple(reversed(arms))
        for arm in order:
            metric=out/(case.replace("/","_")+"-"+arm+"-"+str(rep)+".callgrind")
            command=["valgrind","--tool=callgrind","--quiet","--cache-sim=no",
                     "--branch-sim=no","--callgrind-out-file="+str(metric),
                     str(exes[arm]),*flags]
            with path.open("rb") as src:
                p=subprocess.run(command,stdin=src,stdout=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE,timeout=900)
            assert p.returncode==0,(case,arm,p.returncode,p.stderr[-400:])
            ir=next((int(s.split()[1]) for s in metric.read_text().splitlines()
                     if s.startswith("summary: ")),None)
            assert ir is not None and ir>1_000_000,(case,arm,ir)
            data[arm].append(ir)
            metric.unlink()
    med={arm:statistics.median(data[arm]) for arm in arms}
    ratio=med["unified"]/med["base"]
    result={"test":case,"raw_guest_ir":data,"median_guest_ir":med,"candidate_over_base":ratio}
    results.append(result)
    print("FLASH_VNEXT_CASE="+json.dumps(result),flush=True)
geo=math.exp(sum(math.log(x["candidate_over_base"]) for x in results)/len(results))
worst=max(x["candidate_over_base"] for x in results)
decision="FULL_MATHLIB_GATE" if geo<=0.99 and worst<=1.01 else "NO_MATERIAL_SMALL_CASE_GAIN"
report={
 "upstream_sha":"7645b1e1fcacfe410c99141f1234381d995b325d",
 "experiment":"one contextual cache entry for type and value, independent checking authorities",
 "common_patches":"source-pinned sparse touched-slot reset and 4x PtrMap growth",
 "validity":"Source/portable196 correctness only; no proof of general kernel soundness",
 "portables":counts,"metric":"Callgrind full-process guest Ir, not hardware retired instructions",
 "geometric_ratio":geo,"worst_case_ratio":worst,
 "cases":results,"decision":decision,"full_mathlib_qualified":False,"official_rank_qualified":False,
 "binary_sha256":{n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in exes.items()}
}
(out/"decision.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("FLASH_VNEXT_DECISION="+json.dumps({"decision":decision,"geo":geo,"worst":worst}),flush=True)
