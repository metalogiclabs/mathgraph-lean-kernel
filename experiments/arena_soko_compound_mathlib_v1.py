#!/usr/bin/env python3
"""Same-source/same-training full-Mathlib A/B, exact PruneMemo sparse-reset plus 4x PtrMap growth.
Linux CPU/wall/RSS are NOT the Arena hardware retired-instruction counter.
"""
import hashlib,json,os,pathlib,statistics,subprocess,sys,time
export=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
assert export.is_file() and export.stat().st_size>3_000_000_000
bins={"baseline":"/tmp/soko-sparse-base-pgo","candidate":"/tmp/soko-sparse-patch-pgo"}
configs={
 "stdin4":(4,"stdin"),"mmap1":(1,"mmap")
}
events={f"{arm}_{mode}":[] for arm in bins for mode in configs}
normal=["baseline_stdin4","candidate_stdin4","baseline_mmap1","candidate_mmap1"]
for rep in range(2):
    sequence=normal if rep==0 else list(reversed(normal))
    for label in sequence:
        arm,mode=label.split("_",1)
        threads,method=configs[mode]
        cmd=[bins[arm],*(["--stdin"] if method=="stdin" else [str(export)]),
             "--nat-extension","--string-extension","--axiom-allow-all","--threads",str(threads)]
        meter=out/f"{label}-{rep}.time"
        stderr=out/f"{label}-{rep}.stderr"
        stdout=out/f"{label}-{rep}.stdout"
        stream=export.open("rb") if method=="stdin" else subprocess.DEVNULL
        try:
            with stdout.open("wb") as o,stderr.open("wb") as e:
                start=time.monotonic()
                p=subprocess.run(["/usr/bin/time","-f","%U %S %e %M","-o",str(meter),*cmd],
                     stdin=stream,stdout=o,stderr=e,timeout=2400)
                wall=time.monotonic()-start
        finally:
            if method=="stdin":stream.close()
        vals=meter.read_text().strip().splitlines()[-1].split()
        assert len(vals)==4,(label,vals)
        u,s,_,rss=map(float,vals)
        row={"repetition":rep,"exit":p.returncode,"cpu_seconds":u+s,"wall_seconds":wall,
             "max_rss_kb":int(rss),"stdout_sha256":hashlib.sha256(stdout.read_bytes()).hexdigest()}
        events[label].append(row)
        print("COMPOUND_MATHLIB_CASE="+json.dumps({"arm":arm,"mode":mode,**row}),flush=True)
        assert p.returncode==0,(label,row,stderr.read_text(errors="replace")[-1500:])
assert len({e["stdout_sha256"] for runs in events.values() for e in runs})==1,events
summary={name:{"cpu_median_s":statistics.median(x["cpu_seconds"] for x in runs),
              "wall_median_s":statistics.median(x["wall_seconds"] for x in runs),
              "peak_rss_kb":max(x["max_rss_kb"] for x in runs)}
         for name,runs in events.items()}
ratios={}
for mode in configs:
    a=summary["baseline_"+mode];b=summary["candidate_"+mode]
    ratios[mode]={"baseline_over_candidate_cpu":a["cpu_median_s"]/b["cpu_median_s"],
                  "baseline_over_candidate_wall":a["wall_median_s"]/b["wall_median_s"],
                  "candidate_over_baseline_rss":b["peak_rss_kb"]/a["peak_rss_kb"]}
report={"source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
        "arena":"leanprover/lean-kernel-arena@b83254de5146ef34147ab82a48edbe1856b0edcc",
        "candidate_patch":"PruneMemo exact touched-slot reset plus PtrMap 2x->4x growth",
        "experiment":os.environ.get("GITHUB_SHA"),"full_mathlib_accepted_all":True,
        "instruction_counter":"UNAVAILABLE_ON_HOST; needs official independent PMU authority",
        "official_rank_qualified":False,"events":events,"summary":summary,"ratios":ratios}
(out/"compound-full-mathlib.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("COMPOUND_MATHLIB_SUMMARY="+json.dumps({"summary":summary,"ratios":ratios}),flush=True)
