#!/usr/bin/env python3
"""Four-source factorial of two semantics-preserving context transport operations.

Each arm uses the same upstream source, qualified common micro-patches,
same compiler and executable arguments. Protect the whole exact 196 portable
Arena cases before considering proxy guest instructions. Seven matched repeats of each Callgrind arm characterize process-layout
outliers without silently deleting inconvenient observations.

NOT a Lean soundness theorem, full-Mathlib result, or official PMU result.
"""
import hashlib,json,math,pathlib,statistics,subprocess,sys
root,out=map(pathlib.Path,sys.argv[1:3]);out.mkdir(parents=True,exist_ok=True)
arms=("base","fused","support","compound")
bins={n:pathlib.Path("/tmp/flash-compound-"+n+"-target/release/sokonanoda") for n in arms}
flags=["--stdin","--nat-extension","--string-extension","--axiom-allow-all","--threads","4"]
for n,p in bins.items():assert p.is_file(),(n,p)
cases=[(k,p) for k in ("good","bad") for p in sorted((root/k).rglob("*.ndjson"))]
assert len(cases)==196 and sum(k=="good" for k,p in cases)==125 and sum(k=="bad" for k,p in cases)==71
verdicts=[]
for kind,p in cases:
    row={"file":str(p.relative_to(root)),"kind":kind,
         "sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
    for n,exe in bins.items():
        with p.open("rb") as inp:
            q=subprocess.run([str(exe),*flags],stdin=inp,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=100)
        row[n]=q.returncode
        assert q.returncode in (0,1,2),(row,q.stderr[-600:])
        assert (q.returncode==0) if kind=="good" else (q.returncode!=0),row
    assert len({row[n] for n in arms})==1,row
    verdicts.append(row)
counts={str(k):sum(v["base"]==k for v in verdicts) for k in (0,1,2)}
assert counts=={"0":125,"1":69,"2":2},counts
(out/"frozen196.json").write_text(json.dumps({"counts":counts,"rows":verdicts},indent=2)+"\n")
print("FLASH_ROBUST_PROTECTED="+json.dumps(counts),flush=True)

tests=("init-prelude","perf/grind-ring-5","perf/magma-list-pair-n7",
       "perf/magma-list-deep-n21","perf/fueled-chain")
measurements=[]
for t_idx,test in enumerate(tests):
    file=root/"good"/(test+".ndjson")
    assert file.is_file(),test
    rows={n:[] for n in arms}
    for rep in range(7):
        order=list(arms[(rep+t_idx)%len(arms):]+arms[:(rep+t_idx)%len(arms)])
        if rep % 2:order.reverse()
        for arm in order:
            dest=out/(test.replace("/","_")+"-"+arm+"-"+str(rep)+".callgrind")
            cmd=["valgrind","--tool=callgrind","--quiet","--cache-sim=no",
                 "--branch-sim=no","--callgrind-out-file="+str(dest),str(bins[arm]),*flags]
            with file.open("rb") as f:
                run=subprocess.run(cmd,stdin=f,stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE,timeout=900)
            assert run.returncode==0,(test,arm,rep,run.returncode,run.stderr[-800:])
            ir=next((int(x.split()[1]) for x in dest.read_text().splitlines()
                     if x.startswith("summary: ")),None)
            assert ir and ir>1000000,(test,arm,rep,ir)
            rows[arm].append(ir)
            dest.unlink()
    med={arm:statistics.median(vals) for arm,vals in rows.items()}
    ratios={arm:med[arm]/med["base"] for arm in arms[1:]}
    variation={arm:{"min_over_median":min(vals)/med[arm],"max_over_median":max(vals)/med[arm],"median_abs_deviation":statistics.median(abs(v-med[arm]) for v in vals),"n":len(vals)} for arm,vals in rows.items()}
    rec={"test":test,"raw_Ir":rows,"medians":med,"ratios":ratios,"variation":variation}
    measurements.append(rec)
    print("FLASH_ROBUST_CASE="+json.dumps(rec),flush=True)

geo={n:math.exp(sum(math.log(r["ratios"][n]) for r in measurements)/len(measurements)) for n in arms[1:]}
worst={n:max(r["ratios"][n] for r in measurements) for n in arms[1:]}
eligible=[n for n in arms[1:] if geo[n]<=0.99 and worst[n]<=1.01]
winner=min(eligible,key=lambda n:geo[n]) if eligible else None
report={"source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
        "base":"identical sparse touched-slot reset plus 4x PtrMap growth",
        "interventions":{"fused":"one projection shared by cache and lambda/Pi closures",
                         "support":"use parent App support to infer application children",
                         "compound":"fused and support together"},
        "metric":"Valgrind Callgrind whole-process guest Ir; not PMU",
        "repeats":7,"protected_verdicts":counts,"measurements":measurements,
        "geometric_ratio":geo,"worst_case_ratio":worst,
        "candidate_for_full_mathlib":winner,
        "decision":"GO_FULL_MATHLIB_AB" if winner else "NO_MATERIAL_FIVE_CASE_GAIN",
        "official_rank_qualified":False,"full_mathlib_qualified":False,
        "binary_sha256":{n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in bins.items()}}
(out/"decision.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("FLASH_ROBUST_DECISION="+json.dumps({"decision":report["decision"],"ratios":geo,
      "worst":worst,"winner":winner}),flush=True)
