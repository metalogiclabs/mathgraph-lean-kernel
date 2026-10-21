#!/usr/bin/env python3
"""Exact same Soko-derived Flash binary: four vs one checking worker.

The Arena sorts by hardware retired instructions after correctness, NOT by
wall time. A one-worker run may avoid duplicated session caches and contention.
No assumption of benefit: test it on the ORIGINAL complete 6.18GB Mathlib.

This experiment reports native CPU/wall/RSS + full-process Callgrind guest Ir.
Guest Ir is a proxy and is NOT Arena hardware retired instructions.
"""
import hashlib
import json
import pathlib
import re
import statistics
import subprocess
import sys
import time

exports, portable, out = map(pathlib.Path,sys.argv[1:])
out.mkdir(parents=True,exist_ok=True)
EXPECTED_SHA="22c5de83469408950005589a3bc5ef5157c65549b5a802f85d567c29151306a6"
assert exports.stat().st_size==6184415052,exports.stat().st_size
with exports.open("rb") as f:
    sha=hashlib.file_digest(f,"sha256").hexdigest()
assert sha==EXPECTED_SHA,sha
exe=pathlib.Path("/tmp/flash-workers-pgo")
assert exe.is_file()
binary_sha=hashlib.sha256(exe.read_bytes()).hexdigest()
prefix=["--stdin","--nat-extension","--string-extension","--axiom-allow-all"]
opt=lambda w: [str(exe),*prefix,"--threads",str(w)]
cases=[(kind,p) for kind in ("good","bad") for p in sorted((portable/kind).rglob("*.ndjson"))]
assert sum(k=="good" for k,_ in cases)==125
assert sum(k=="bad" for k,_ in cases)==71
verdicts=[]
for kind,src in cases:
    row={"source":str(src.relative_to(portable)),"group":kind}
    for worker in (1,4):
        with src.open("rb") as inp:
            p=subprocess.run(opt(worker),stdin=inp,stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE,timeout=150)
        row[str(worker)]=p.returncode
        assert p.returncode in (0,1,2),(row,p.stderr[-400:])
        assert (p.returncode==0) if kind=="good" else (p.returncode!=0),row
    assert row["1"]==row["4"],row
    verdicts.append(row)
counts={str(k):sum(x["1"]==k for x in verdicts) for k in (0,1,2)}
assert counts=={"0":125,"1":69,"2":2},counts
(out/"protected196.json").write_text(json.dumps({"counts":counts,"cases":verdicts},indent=2)+"\n")
print("FLASH_WORKERS_PROTECTED="+json.dumps(counts),flush=True)

native={"1":[],"4":[]}
for rep,order in enumerate(((4,1),(1,4))):
    for workers in order:
        out_prefix=out/f"workers{workers}-native-{rep}"
        stdout=pathlib.Path(str(out_prefix)+".stdout")
        stderr=pathlib.Path(str(out_prefix)+".stderr")
        meter=pathlib.Path(str(out_prefix)+".time")
        args=["/usr/bin/time","-f","%U %S %e %M","-o",str(meter),*opt(workers)]
        start=time.monotonic()
        with exports.open("rb") as inp,stdout.open("wb") as sout,stderr.open("wb") as serr:
            p=subprocess.run(args,stdin=inp,stdout=sout,stderr=serr,timeout=3000)
        wall=time.monotonic()-start
        assert p.returncode==0,(workers,rep,p.returncode,stderr.read_text(errors="replace")[-2000:])
        vals=meter.read_text().strip().splitlines()[-1].split()
        assert len(vals)==4,vals
        user,syscpu,_,rss=map(float,vals)
        row={"repetition":rep,"cpu_seconds":user+syscpu,"wall_seconds":wall,
             "max_rss_kb":int(rss),
             "stdout_sha256":hashlib.sha256(stdout.read_bytes()).hexdigest()}
        native[str(workers)].append(row)
        print("FLASH_WORKERS_NATIVE="+json.dumps({"workers":workers,**row}),flush=True)
assert len({r["stdout_sha256"] for rows in native.values() for r in rows})==1

whole_process_ir={}
for workers in (4,1):
    outpath=out/f"workers{workers}.callgrind"
    cmd=["valgrind","--tool=callgrind","--cache-sim=no","--branch-sim=no",
         "--callgrind-out-file="+str(outpath),*opt(workers)]
    begin=time.monotonic()
    stderr=out/f"workers{workers}-callgrind.stderr"
    with exports.open("rb") as inp,stderr.open("wb") as err:
        proc=subprocess.run(["timeout","7000s",*cmd],stdin=inp,
            stdout=subprocess.DEVNULL,stderr=err,timeout=7100)
    assert proc.returncode==0,(workers,"MATHLIB_NOT_ACCEPTED",proc.returncode,
                               stderr.read_text(errors="replace")[-1600:])
    match=re.search(r"^summary:\s*(\d+)\s*$",outpath.read_text(),re.M)
    assert match,(workers,"NO_COUNT")
    total=int(match.group(1))
    assert total>10_000_000_000,(workers,total)
    profiler=subprocess.run(["callgrind_annotate","--inclusive=no","--threshold=1",
                             str(outpath)],capture_output=True,text=True,timeout=240)
    if profiler.returncode==0:
        (out/f"workers{workers}-hotspots.txt").write_text(profiler.stdout)
    outpath.unlink()
    whole_process_ir[str(workers)]={"accepted":True,"guest_Ir":total,
                                     "instrumented_wall_s":time.monotonic()-begin}
    (out/"progress.json").write_text(json.dumps(whole_process_ir,indent=2)+"\n")
    print("FLASH_WORKERS_FULL_IR="+json.dumps({"workers":workers,**whole_process_ir[str(workers)]}),flush=True)

ratio=whole_process_ir["1"]["guest_Ir"]/whole_process_ir["4"]["guest_Ir"]
summary={w:{"median_native_cpu_s":statistics.median(r["cpu_seconds"] for r in rows),
            "median_native_wall_s":statistics.median(r["wall_seconds"] for r in rows),
            "max_rss_kb":max(r["max_rss_kb"] for r in rows)}
         for w,rows in native.items()}
report={"source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
        "common_changes":"qualified sparse touched-slot reset + PtrMap 4x growth",
        "binary_sha256":binary_sha,"exact_mathlib_sha256":EXPECTED_SHA,
        "tested_difference":"runtime number of checking workers only: one vs four",
        "pgo_training":"same init-prelude 4-worker profile for both checker runs",
        "protected196":counts,"native":native,"native_summary":summary,
        "full_mathlib":whole_process_ir,"one_over_four_guest_Ir":ratio,
        "instruction_saving_fraction":1-ratio,
        "candidate_for_official_PMU":ratio<0.90,
        "official_rank_qualified":False,
        "note":"Callgrind guest Ir is NOT official Arena PMU hardware retired instructions"}
(out/"decision.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("FLASH_WORKERS_FULL_DECISION="+json.dumps({"one_over_four_ratio":ratio,
        "saving":1-ratio,"candidate_for_official_PMU":ratio<0.90}),flush=True)
