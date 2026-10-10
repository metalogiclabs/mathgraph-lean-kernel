#!/usr/bin/env python3
"""Verify every portable positive and negative for an attributed serial checker.
No whitelist or fixture-dependent fallback is allowed.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import statistics
import time

root=Path(sys.argv[1])
out=Path(sys.argv[2])
out.mkdir(parents=True,exist_ok=True)
cfg=["--stdin","--nat-extension","--string-extension","--axiom-allow-all"]
soko=os.environ.get("SOKO_BIN","/tmp/msi-leader.bin")
flash=os.environ.get("FLASH_BIN","/tmp/msi-before.bin")
router=Path("experiments/arena_serial_hybrid_v1.sh").resolve()
modes={
    "serial_primary":[soko,*cfg,"--threads","1"],
    "serial_router":["bash",str(router)],
    "parallel_primary":[soko,*cfg,"--threads","4"],
}
assert router.is_file()
cases=[("good",p) for p in sorted((root/"good").rglob("*.ndjson"))]+[
       ("bad",p) for p in sorted((root/"bad").rglob("*.ndjson"))]
assert sum(b=="good" for b,_ in cases)>=125 and sum(b=="bad" for b,_ in cases)>=71
observations=[]
for bucket,path in cases:
    data=path.read_bytes()
    records={}
    for name,cmd in modes.items():
        if name=="serial_router":
            args=[*cmd,str(path)]
            p=subprocess.run(args,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=80)
        else:
            p=subprocess.run(cmd,input=data,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=80)
        records[name]=p.returncode
    desired=0 if bucket=="good" else 1
    if records["serial_router"]!=desired:
        raise AssertionError((str(path),records,desired))
    if records["serial_primary"] in (0,1):
        assert records["serial_router"]==records["serial_primary"],(str(path),records)
    assert records["serial_primary"]==records["parallel_primary"],(str(path),records)
    observations.append({"case":str(path.relative_to(root)),"outcomes":records,
        "fallback":records["serial_primary"] in (2,3)})
fallback=[x["case"] for x in observations if x["fallback"]]
print("MSI_HYBRID_CORRECT="+json.dumps({"tested":len(cases),
      "bad":sum(b=="bad" for b,_ in cases),
      "good":sum(b=="good" for b,_ in cases),"fallback_cases":fallback}),flush=True)
(out/"portable.json").write_text(json.dumps({"source":os.environ["GITHUB_SHA"],
    "primary":"sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
    "fallback":"MathGraph Flash@78c7502bac8a5ba000057b3f083bc0595ac65750",
    "scope":"portable fixed-outcome corpus, not full Mathlib",
    "rows":observations},indent=2)+"\n")

focus=["init-prelude","perf/fueled-chain","perf/grind-ring-5","perf/magma-list-deep-n21"]
times={}
for name in ("serial_primary","parallel_primary","serial_router"):
    subset=[]
    for case in focus:
        file=root/"good"/(case+".ndjson")
        if not file.exists():
            continue
        t=[]
        for _ in range(2):
            start=time.monotonic()
            if name=="serial_router":
                p=subprocess.run([*modes[name],str(file)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=80)
            else:
                with file.open("rb") as source:
                    p=subprocess.run(modes[name],stdin=source,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=80)
            t.append(time.monotonic()-start)
            assert p.returncode==0,(name,case,p.stderr[-500:])
        subset.append({"case":case,"median_wall_seconds":statistics.median(t),"repetitions":t})
    times[name]=subset
print("MSI_HYBRID_PORTABLE_PERF="+json.dumps(times),flush=True)
(out/"portable-performance.json").write_text(json.dumps(
    {"metric":"wall only; not Arena instructions","results":times},indent=2)+"\n")
