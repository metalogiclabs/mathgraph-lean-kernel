#!/usr/bin/env python3
"""Diagnose Mathlib declaration-level time using upstream reporting fork.
This is an instrumentation-only cost atlas, not an Arena instruction score.
"""
import json,os,pathlib,re,subprocess,sys,time
source=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
assert source.is_file() and source.stat().st_size==6184415052,"Require exact-size Mathlib"
command=["/tmp/soko-decl-hotspot","--stdin","--nat-extension","--string-extension",
         "--axiom-allow-all","--threads","1","--verbose"]
logs=out/"declarations.txt"
stderr=out/"stderr.txt"
with source.open("rb") as fin,logs.open("wb") as fo,stderr.open("wb") as fe:
    started=time.monotonic()
    p=subprocess.run(command,stdin=fin,stdout=fo,stderr=fe,timeout=2700)
    wall=time.monotonic()-started
assert p.returncode==0,("MATHLIB_NOT_ACCEPTED",p.returncode,stderr.read_text(errors="replace")[-1700:])
pattern=re.compile(r"^\s*\d+/\d+\s+ok\s+(\S+)\s+([\d.]+)ms\s+(.+)$")
rows=[];count_by_kind={};sum_by_kind={}
with logs.open("r",encoding="utf-8",errors="replace") as fin:
    for line in fin:
        match=pattern.match(line)
        if match is None: continue
        kind,ms,name=match.groups();cost=float(ms)
        rows.append({"name":name,"kind":kind,"ms":cost})
        count_by_kind[kind]=count_by_kind.get(kind,0)+1
        sum_by_kind[kind]=sum_by_kind.get(kind,0)+cost
assert len(rows)>=1000,("MISSING_DECLARATION_TIMINGS",len(rows),logs.stat().st_size)
rows.sort(key=lambda row:row["ms"],reverse=True)
total=sum(row["ms"] for row in rows)
report={
 "authority":"intgrah/sokonanoda@e648a9f7dfafd0fae67ba087007fcd8d6157a365",
 "arena":"leanprover/lean-kernel-arena@b83254de5146ef34147ab82a48edbe1856b0edcc",
 "experimental_instrumentation":"upstream --verbose per-declaration time, single worker",
 "not_scoring_authority":True,"output_verdict":"ACCEPT","wall_seconds":wall,
 "count":len(rows),"reported_sum_ms":total,
 "by_kind":{kind:{"count":count_by_kind[kind],"ms":sum_by_kind[kind]} for kind in count_by_kind},
 "top_100":rows[:100],
 "top_10_fraction":sum(x["ms"] for x in rows[:10])/total if total else 0,
 "top_100_fraction":sum(x["ms"] for x in rows[:100])/total if total else 0,
 "official_rank_qualified":False}
(out/"declaration-cost-atlas.json").write_text(json.dumps(report,indent=2)+"\n")
print("DECLARATION_ATLAS_SUMMARY="+json.dumps({
 "count":len(rows),"wall_seconds":wall,"top10_fraction":report["top_10_fraction"],
 "top100_fraction":report["top_100_fraction"],
 "top":rows[:12],"official_rank_qualified":False}),flush=True)
logs.unlink()
