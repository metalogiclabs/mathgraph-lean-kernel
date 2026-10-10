#!/usr/bin/env python3
"""Holdout: same PGO checker and exact Mathlib, vary only stdin vs read-only mmap.

Linux CPU/wall are direct observations, not Arena retired instructions.
Neither partial export nor proxy instruction counts grant an official #1 claim.
"""
import json, os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import hashlib

source=Path(sys.argv[1]); out=Path(sys.argv[2]); out.mkdir(parents=True,exist_ok=True)
assert source.is_file() and source.stat().st_size>3_000_000_000
binary="/tmp/msi-mathlib-mmap-soko"
args=["--nat-extension","--string-extension","--axiom-allow-all"]
modes={
    "stdin1":("stdin",1),"mmap1":("mmap",1),
    "stdin4":("stdin",4),"mmap4":("mmap",4)
}
events={name:[] for name in modes}
for repetition in range(2):
    order=["stdin1","mmap1","stdin4","mmap4"] if repetition==0 else [
        "mmap4","stdin4","mmap1","stdin1"]
    for name in order:
        method,threads=modes[name]
        cmd=([binary,"--stdin",*args,"--threads",str(threads)]
            if method=="stdin" else [binary,str(source),*args,"--threads",str(threads)])
        meter=out/f"time-{name}-{repetition}.txt"
        stdout=out/f"stdout-{name}-{repetition}.txt"
        stderr=out/f"stderr-{name}-{repetition}.txt"
        stream=source.open("rb") if method=="stdin" else subprocess.DEVNULL
        try:
            with stdout.open("wb") as sout, stderr.open("wb") as serr:
                start=time.monotonic()
                p=subprocess.run(["/usr/bin/time","-f","%U %S %e %M",
                                  "-o",str(meter),*cmd],
                                 stdin=stream,stdout=sout,stderr=serr,timeout=2400)
                elapsed=time.monotonic()-start
        finally:
            if method=="stdin": stream.close()
        vals=meter.read_text().strip().splitlines()[-1].split()
        assert len(vals)==4,(name,vals)
        user,system,reported_wall,rss=map(float,vals)
        row={"repetition":repetition,"verdict":p.returncode,
            "wall_seconds":elapsed,"cpu_seconds":user+system,"rss_kb":int(rss),
            "stdout_sha256":hashlib.sha256(stdout.read_bytes()).hexdigest()}
        events[name].append(row)
        print("MSI_MMAP_MATHLIB_CASE="+json.dumps({"mode":name,**row}),flush=True)
        assert p.returncode==0,(name,row,stderr.read_text(errors="replace")[-1800:])

assert len({v["stdout_sha256"] for values in events.values() for v in values})==1,events
summary={key:{"median_wall_seconds":statistics.median(x["wall_seconds"] for x in val),
              "median_cpu_seconds":statistics.median(x["cpu_seconds"] for x in val),
              "max_rss_kb":max(x["rss_kb"] for x in val)}
         for key,val in events.items()}
pairings={}
for workers in (1,4):
    pairings[str(workers)]={
       "mmap_over_stdin_cpu":summary[f"mmap{workers}"]["median_cpu_seconds"]/
          summary[f"stdin{workers}"]["median_cpu_seconds"],
       "mmap_over_stdin_wall":summary[f"mmap{workers}"]["median_wall_seconds"]/
          summary[f"stdin{workers}"]["median_wall_seconds"],
    }
print("MSI_MMAP_MATHLIB_SUMMARY="+json.dumps({"medians":summary,"pairings":pairings}),flush=True)
result={"source_revision":"7645b1e1fcacfe410c99141f1234381d995b325d",
        "arena_revision":"b83254de5146ef34147ab82a48edbe1856b0edcc",
        "experiment_revision":os.environ["GITHUB_SHA"],
        "file_bytes":source.stat().st_size,
        "metric":"CPU + wall on exact full Mathlib export, NOT Arena retired instructions",
        "qualified_full_mathlib":True,
        "official_rank_qualified":False,
        "runs":events,"medians":summary,"pairings":pairings}
(out/"heldout.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
