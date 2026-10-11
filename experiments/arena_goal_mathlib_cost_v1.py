#!/usr/bin/env python3
"""Full-Mathlib, source-pinned PGO and deterministic guest-Ir decision.

Exact input, ISA, training and process boundary for all compared arms.
All arms must ACCEPT the same original full Mathlib. Whole-process Callgrind
guest Ir is a developmental proxy ONLY, not Arena retired hardware
instructions. No release or rank claim is produced here.
"""
import hashlib,json,os,pathlib,re,statistics,subprocess,sys,time

data=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2])
arms=tuple(sys.argv[3].split(","))
assert arms[0]=="baseline" and len(arms) in (2,3) and len(set(arms))==len(arms)
assert set(arms).issubset({"baseline","root","chain"})
out.mkdir(parents=True,exist_ok=True)
export_size=6184415052
export_sha="22c5de83469408950005589a3bc5ef5157c65549b5a802f85d567c29151306a6"
arena="leanprover/lean-kernel-arena@b83254de5146ef34147ab82a48edbe1856b0edcc"
source="intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d"
assert data.is_file() and data.stat().st_size==export_size,("EXACT_EXPORT_SIZE_FAILED",data)
h=hashlib.sha256()
with data.open("rb") as fin:
    for block in iter(lambda:fin.read(8*1024*1024),b""):
        h.update(block)
assert h.hexdigest()==export_sha,("EXACT_EXPORT_SHA_FAILED",h.hexdigest())
opts=["--stdin","--nat-extension","--string-extension","--axiom-allow-all","--threads","4"]
native={a:[] for a in arms}
# Symmetric serial order reduces simple host drift for native CPU/RSS.
order=list(arms)+list(reversed(arms))
for arm in order:
    binary="/tmp/goal-mathlib-"+arm+".bin"
    suffix=arm+"-"+str(len(native[arm]))
    costfile=out/(suffix+".time")
    cmd=["/usr/bin/time","-f","cpu_user=%U\ncpu_system=%S\npeak_rss_kb=%M",
         "-o",str(costfile),binary,*opts]
    start=time.monotonic()
    with data.open("rb") as fin:
        run=subprocess.run(cmd,stdin=fin,stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE,timeout=2400)
    wall=time.monotonic()-start
    assert run.returncode==0,("MATHLIB_NATIVE_NOT_ACCEPTED",arm,run.returncode,
                              run.stderr[-1200:].decode(errors="replace"))
    observed={}
    for line in costfile.read_text().splitlines():
        k,sep,v=line.partition("=")
        if sep: observed[k]=float(v)
    assert all(k in observed for k in ("cpu_user","cpu_system","peak_rss_kb"))
    observed["wall_seconds"]=round(wall,3)
    observed["cpu_seconds"]=observed["cpu_user"]+observed["cpu_system"]
    native[arm].append(observed)
    print("MG_GOAL_FULL_NATIVE="+json.dumps({"arm":arm,"data":observed}),flush=True)
    costfile.unlink()

profiles={}
for arm in arms:
    binary="/tmp/goal-mathlib-"+arm+".bin"
    path=out/(arm+".callgrind")
    stderr=out/(arm+".valgrind-stderr")
    cmd=["valgrind","--tool=callgrind","--cache-sim=no","--branch-sim=no",
         "--callgrind-out-file="+str(path),binary,*opts]
    start=time.monotonic()
    with data.open("rb") as fin, stderr.open("wb") as serr:
        run=subprocess.run(cmd,stdin=fin,stdout=subprocess.DEVNULL,
                           stderr=serr,timeout=7500)
    assert run.returncode==0,("MATHLIB_GUEST_IR_NOT_ACCEPTED",arm,
                              run.returncode,stderr.read_bytes()[-1500:].decode(errors="replace"))
    m=re.search(r"^summary:\s*(\d+)\s*$",path.read_text(),re.M)
    assert m,("MISSING_CALLGRIND_INSTRUCTIONS",arm,path.stat().st_size)
    instructions=int(m.group(1))
    assert instructions>100_000_000_000,("IMPOSSIBLY_LOW_FULL_EXPORT_INSTRUCTIONS",arm,instructions)
    annot=subprocess.run(["callgrind_annotate","--inclusive=no","--threshold=95",str(path)],
                         text=True,capture_output=True,timeout=400)
    if annot.returncode==0:
        (out/(arm+"-exclusive-hotspots.txt")).write_text(annot.stdout)
    profiles[arm]={"accepted":True,"callgrind_guest_ir":instructions,
                   "wall_seconds_with_valgrind":round(time.monotonic()-start,3),
                   "hotspot_profile_available":annot.returncode==0}
    (out/"progress.json").write_text(json.dumps({"native":native,"profiles":profiles,
                              "no_official_rank_claim":True},indent=2)+"\n")
    print("MG_GOAL_FULL_GUEST_IR="+json.dumps({"arm":arm,**profiles[arm]}),flush=True)
    path.unlink()
    stderr.unlink()

parent=profiles["baseline"]["callgrind_guest_ir"]
decisions={}
for arm in arms[1:]:
    ir=profiles[arm]["callgrind_guest_ir"]/parent
    rss=max(x["peak_rss_kb"] for x in native[arm])/max(x["peak_rss_kb"] for x in native["baseline"])
    cpu=statistics.median(x["cpu_seconds"] for x in native[arm])/statistics.median(x["cpu_seconds"] for x in native["baseline"])
    wall=statistics.median(x["wall_seconds"] for x in native[arm])/statistics.median(x["wall_seconds"] for x in native["baseline"])
    decisions[arm]={"full_guest_ir_ratio":ir,"guest_ir_saving":1-ir,
                    "max_native_rss_ratio":rss,"native_cpu_ratio":cpu,
                    "native_wall_ratio":wall,
                    "qualifies_as_developmental_full_mathlib_instruction_gain":
                    bool(ir <= 0.99 and rss<=1.10)}
best=min(arms[1:],key=lambda a:decisions[a]["full_guest_ir_ratio"])
report={"arena":arena,"upstream_source":source,"mathlib_sha256":export_sha,
        "mathlib_size_bytes":export_size,
        "proof_semantics":"All candidates use source-typed dependent checking and original full inference fallback",
        "common_parent":"pinned touched-slot sparse reset and 4x PtrMap growth",
        "source_head":os.environ.get("GITHUB_SHA"),
        "flags":opts,"pgo":"each arm independently trained on exact 4-worker init-prelude same ISA",
        "candidate_arms":list(arms),"native_repeated_measurements":native,
        "full_mathlib_callgrind":profiles,"decisions":decisions,"best_candidate":best,
        "any_warranted_developmental_full_mathlib_gain":
        decisions[best]["qualifies_as_developmental_full_mathlib_instruction_gain"],
        "hardware_pmu_retired_instructions":None,
        "official_rank_qualified":False,
        "note":"Software guest-Ir comparisons never establish an Arena PMU win or Nucleus acceptance."}
(out/"report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("MG_GOAL_FULL_DECISION="+json.dumps({"best":best,"decisions":decisions,
    "official_rank_qualified":False}),flush=True)
