#!/usr/bin/env python3
"""Compute same-source Valgrind Callgrind guest-instruction comparisons.
NOT hardware retired instructions and NOT official Arena score.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

root=Path(sys.argv[1])
out=Path(sys.argv[2])
out.mkdir(parents=True,exist_ok=True)
binary=os.environ.get("SOKO_BIN","/tmp/msi-leader.bin")
assert Path(binary).is_file()
cases=["perf/grind-ring-5","perf/magma-list-deep-n21",
       "perf/magma-list-pair-n7","perf/fueled-chain"]
workers=[1,2,4]
rows=[]
for case in cases:
    path=root/"good"/(case+".ndjson")
    assert path.is_file(),path
    measurements={}
    for threads in workers:
        report=out/(case.replace("/","_")+"-"+str(threads)+".callgrind")
        argv=[
            "valgrind","--tool=callgrind","--cache-sim=no","--branch-sim=no",
            "--callgrind-out-file="+str(report),
            binary,"--stdin","--nat-extension","--string-extension",
            "--axiom-allow-all","--threads",str(threads)
        ]
        with path.open("rb") as fin:
            result=subprocess.run(argv,stdin=fin,stdout=subprocess.DEVNULL,
                                  stderr=subprocess.PIPE,timeout=480)
        if result.returncode!=0:
            raise RuntimeError((case,threads,result.returncode,result.stderr[-1200:]))
        text=report.read_text()
        m=re.search(r"^summary:\s*(\d+)\s*$",text,re.MULTILINE)
        if not m:
            raise AssertionError((report,text[-700:]))
        measurements[str(threads)]=int(m.group(1))
        print("MSI_CALLGRIND_CASE="+json.dumps(
            {"case":case,"threads":threads,"guest_Ir":measurements[str(threads)]}),flush=True)
    rows.append({"case":case,"guest_Ir":measurements,
      "one_over_four":measurements["1"]/measurements["4"]})
out.joinpath("summary.json").write_text(json.dumps({
    "source_sha":"7645b1e1fcacfe410c99141f1234381d995b325d",
    "metric":"Valgrind guest instructions Ir, NOT hardware retired instructions",
    "cases":rows,
},indent=2)+"\n")
print("MSI_CALLGRIND_SUMMARY="+json.dumps(
    [{"case":r["case"],"one_over_four":r["one_over_four"]} for r in rows]),flush=True)
