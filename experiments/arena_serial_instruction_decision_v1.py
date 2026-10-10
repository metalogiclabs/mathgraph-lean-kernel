#!/usr/bin/env python3
"""Causal 1/2/4-worker input-mode comparison, exact checker, pinned corpus.

Callgrind Ir is a guest instruction proxy, NOT hardware retired instructions.
Never promote a ranking claim from this experiment alone.
"""
import json, math, os, pathlib, subprocess, sys
root=pathlib.Path(sys.argv[1]); out=pathlib.Path(sys.argv[2]); out.mkdir(parents=True,exist_ok=True)
exe="/tmp/soko-serial-decision"
opts=["--nat-extension","--string-extension","--axiom-allow-all"]
cases=[("good",p) for p in sorted((root/"good").rglob("*.ndjson"))]+[
       ("bad",p) for p in sorted((root/"bad").rglob("*.ndjson"))]
assert len(cases)==196 and sum(t=="good" for t,_ in cases)==125
arms=[(t,mode) for t in (1,2,4) for mode in ("stdin","mapped")]
def command(path,threads,mode):
    return [exe,*([str(path)] if mode=="mapped" else ["--stdin"]),*opts,"--threads",str(threads)]
def run(path,threads,mode,callgrind=None):
    args=command(path,threads,mode)
    if callgrind:
        args=["valgrind","--tool=callgrind","--quiet","--collect-jumps=no",
              "--callgrind-out-file="+str(callgrind),*args]
    with path.open("rb") as f:
        return subprocess.run(args,stdin=f if mode=="stdin" else subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=360)
counts={}
for bucket,path in cases:
    verdicts={}
    for threads,mode in arms:
        p=run(path,threads,mode)
        verdicts[f"{threads}_{mode}"]=p.returncode
    assert len(set(verdicts.values()))==1,(path,verdicts)
    verdict=next(iter(verdicts.values()))
    assert verdict==0 if bucket=="good" else verdict in (1,2),(path,verdict)
    counts[str(verdict)]=counts.get(str(verdict),0)+1
print("SERIAL_DECISION_VERDICTS="+json.dumps({"count":len(cases),"outcomes":counts,
      "all_six_arms_identical":True}),flush=True)
focus=["init-prelude","perf/grind-ring-5","perf/magma-list-pair-n7",
       "perf/magma-list-deep-n21","perf/fueled-chain"]
records=[]
for case in focus:
    path=root/"good"/(case+".ndjson")
    assert path.is_file(),path
    values={}
    for threads,mode in arms:
        output=out/(case.replace("/","_")+f"-{threads}-{mode}.callgrind")
        p=run(path,threads,mode,output)
        assert p.returncode==0,(case,threads,mode,p.stderr[-700:])
        line=next((l for l in output.read_text().splitlines() if l.startswith("summary: ")),None)
        assert line is not None,(case,threads,mode)
        values[f"{threads}_{mode}"]=int(line.split()[1])
        output.unlink()
    record={"case":case,"guest_instructions":values,
            "serial_over_four_stdin":values["1_stdin"]/values["4_stdin"],
            "serial_over_four_mapped":values["1_mapped"]/values["4_mapped"],
            "mapped_serial_over_streamed_four":values["1_mapped"]/values["4_stdin"]}
    records.append(record)
    print("SERIAL_DECISION_CASE="+json.dumps(record),flush=True)
metrics=["serial_over_four_stdin","serial_over_four_mapped","mapped_serial_over_streamed_four"]
geomeans={k:math.exp(sum(math.log(v[k]) for v in records)/len(records)) for k in metrics}
decision="PROMOTE_TO_NATIVE_MATHLIB_MEASUREMENT" if geomeans["mapped_serial_over_streamed_four"]<0.99 else "NO_DECISIVE_PROXY_WIN"
report={"source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
        "experiment":os.environ["GITHUB_SHA"],"verdict_counts":counts,
        "measure":"Valgrind Callgrind guest Ir, NOT Arena hardware retired instructions",
        "cases":records,"geometric_means":geomeans,"decision":decision,
        "official_rank_qualified":False}
(out/"decision.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("SERIAL_DECISION_SUMMARY="+json.dumps({"geomeans":geomeans,"decision":decision}),flush=True)
