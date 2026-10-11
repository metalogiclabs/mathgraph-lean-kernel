#!/usr/bin/env python3
"""Full-Mathlib Callgrind comparison: exact baseline versus compound cache patch.
Guest Ir is a developmental proxy, never Arena PMU retired instructions.
"""
import hashlib,json,os,pathlib,re,subprocess,sys,time
data=pathlib.Path(sys.argv[1]); out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
expected_size=6184415052
expected_sha="22c5de83469408950005589a3bc5ef5157c65549b5a802f85d567c29151306a6"
assert data.is_file() and data.stat().st_size==expected_size,("MATHLIB_NOT_FROZEN",data.stat().st_size)
h=hashlib.sha256()
with data.open("rb") as f:
    while b:=f.read(8*1024*1024):h.update(b)
assert h.hexdigest()==expected_sha,("MATHLIB_HASH_CHANGED",h.hexdigest())
opts=["--nat-extension","--string-extension","--axiom-allow-all","--threads","4"]
results={}
for arm in ("baseline","compound"):
    binary=f"/tmp/ir-mathlib-{arm}"
    outfile=out/f"{arm}.callgrind"
    cmd=["valgrind","--tool=callgrind","--cache-sim=no","--branch-sim=no",
         "--callgrind-out-file="+str(outfile),binary,str(data),*opts]
    start=time.monotonic()
    stderr=out/f"{arm}.stderr"
    with stderr.open("wb") as serr:
        p=subprocess.run(["timeout","6800s",*cmd],stdout=subprocess.DEVNULL,
                         stderr=serr,timeout=6950)
    assert p.returncode==0,(arm,"FULL_MATHLIB_NOT_ACCEPTED",p.returncode,
                            stderr.read_bytes()[-1200:].decode(errors="replace"))
    summary=re.search(r"^summary:\s*(\d+)\s*$",outfile.read_text(),re.M)
    assert summary is not None,(arm,"CALLGRIND_MISSING_IR")
    ir=int(summary.group(1))
    assert ir>1_000_000_000,("INVALID_INSTRUCTION_EVENT",arm,ir)
    selfprof=subprocess.run(["callgrind_annotate","--inclusive=no","--threshold=0.1",
                             str(outfile)],capture_output=True,text=True,timeout=180)
    assert selfprof.returncode==0,selfprof.stderr[-1000:]
    (out/f"{arm}-self-cost.txt").write_text(selfprof.stdout)
    results[arm]={"accepted":True,"guest_ir":ir,"wall_seconds":time.monotonic()-start}
    (out/"progress.json").write_text(json.dumps({"results":results,"official_rank":False},
                                                 indent=2)+"\n")
    print("MATHLIB_GUEST_IR_CASE="+json.dumps({"arm":arm,**results[arm]}),flush=True)
    outfile.unlink()
ratio=results["compound"]["guest_ir"]/results["baseline"]["guest_ir"]
report={"source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
        "arena":"leanprover/lean-kernel-arena@b83254de5146ef34147ab82a48edbe1856b0edcc",
        "export_sha256":expected_sha,"experiment":os.environ.get("GITHUB_SHA"),
        "metric":"Full-process Valgrind Callgrind guest Ir NOT hardware instructions",
        "records":results,"compound_over_baseline_guest_ir":ratio,
        "instruction_saving_fraction":1-ratio,
        "official_rank_qualified":False}
(out/"report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("MATHLIB_GUEST_IR_SUMMARY="+json.dumps({"ratio":ratio,
      "saving_fraction":1-ratio,"official_rank_qualified":False}),flush=True)
