#!/usr/bin/env python3
"""Exact input-mode comparison for pinned sokonanoda; no checker source differences.

stdin = official four-MiB buffered-reader thread; mmap = positional file path.
Every verdict must match, every valid input accepted, every invalid input not accepted.
Callgrind is a deterministic guest instruction proxy, not Arena hardware retired counts.
"""
import json
import math
import os
from pathlib import Path
import subprocess
import sys

root=Path(sys.argv[1]); evidence=Path(sys.argv[2])
evidence.mkdir(parents=True,exist_ok=True)
binary="/tmp/soko-mmap-binary"
base=["--nat-extension","--string-extension","--axiom-allow-all"]
cases=[("good",p) for p in sorted((root/"good").rglob("*.ndjson"))]+[
       ("bad",p) for p in sorted((root/"bad").rglob("*.ndjson"))]
assert sum(t=="good" for t,_ in cases)==125 and sum(t=="bad" for t,_ in cases)==71

def invoke(path,mode,workers,meter=None):
    if mode=="stdin":
        cmd=[binary,"--stdin",*base,"--threads",str(workers)]
    elif mode=="mapped":
        cmd=[binary,str(path),*base,"--threads",str(workers)]
    else:
        raise RuntimeError(mode)
    if meter is not None:
        cmd=["valgrind","--tool=callgrind","--quiet","--collect-jumps=no",
             "--callgrind-out-file="+str(meter),*cmd]
    source=path.open("rb") if mode=="stdin" else subprocess.DEVNULL
    try:
        proc=subprocess.run(cmd,stdin=source,stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE,timeout=300)
    finally:
        if mode=="stdin": source.close()
    return proc

verdicts=[]
for label,path in cases:
    values={}
    for threads in (1,4):
        for mode in ("stdin","mapped"):
            p=invoke(path,mode,threads)
            values[f"{mode}{threads}"]=p.returncode
    assert len(set(values.values()))==1, (path,values)
    code=values["stdin4"]
    assert code==0 if label=="good" else code in (1,2), (path,values)
    verdicts.append({"case":str(path.relative_to(root)),"exit":code})
print("MSI_MMAP_196="+json.dumps({
    "count":len(verdicts),"accepted_valid":sum(v["exit"]==0 for v in verdicts),
    "invalid_declines":sum(v["exit"]==2 for v in verdicts),
    "all_four_configurations_identical":True
}),flush=True)

focus=["init-prelude","perf/grind-ring-5","perf/magma-list-pair-n7",
       "perf/magma-list-deep-n21","perf/fueled-chain"]
measure=[]
for case in focus:
    path=root/"good"/(case+".ndjson")
    if not path.exists(): continue
    arms={}
    for threads in (1,4):
        for mode in ("stdin","mapped"):
            f=evidence/(case.replace("/","_")+f"-{mode}-{threads}.callgrind")
            proc=invoke(path,mode,threads,meter=f)
            assert proc.returncode==0,(case,mode,threads,proc.stderr[-500:])
            summary=next((int(l.split()[1]) for l in f.read_text().splitlines()
                          if l.startswith("summary: ")),None)
            assert summary is not None and summary>1_000_000,(case,mode,threads,summary)
            arms[f"{mode}{threads}"]=summary
            f.unlink()
    entry={"case":case,"guest_Ir":arms,
           "mmap_over_stream_1":arms["mapped1"]/arms["stdin1"],
           "mmap_over_stream_4":arms["mapped4"]/arms["stdin4"]}
    measure.append(entry)
    print("MSI_MMAP_IR="+json.dumps(entry),flush=True)
gain1=math.exp(sum(math.log(x["mmap_over_stream_1"]) for x in measure)/len(measure))
gain4=math.exp(sum(math.log(x["mmap_over_stream_4"]) for x in measure)/len(measure))
decision="GO_MATHLIB" if min(gain1,gain4)<0.99 and all(min(x["mmap_over_stream_1"],x["mmap_over_stream_4"])<=1.02 for x in measure) else "NO_MATERIAL_BOUNDED_GAIN"
summary={"source_sha":"7645b1e1fcacfe410c99141f1234381d995b325d",
         "arena_corpus":"11505862349", "source_identical":True,
         "counter":"Callgrind guest Ir; not Arena hardware retired instructions",
         "mmap_geomean_ratio_1":gain1,"mmap_geomean_ratio_4":gain4,
         "decision":decision,"cases":measure,"verdicts":verdicts}
(evidence/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
print("MSI_MMAP_DECISION="+json.dumps({"decision":decision,"geomean1":gain1,"geomean4":gain4}),flush=True)
