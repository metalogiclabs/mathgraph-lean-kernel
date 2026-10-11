#!/usr/bin/env python3
"""Recover unfolded-cache growth evidence; no scoring claims."""
import json,pathlib,re,subprocess,sys
root=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
bin="/tmp/soko-grow-census-checker"
focus=["perf/grind-ring-5","perf/magma-list-pair-n7","perf/magma-list-deep-n21","perf/fueled-chain"]
record=[]
for case in focus:
    path=root/"good"/(case+".ndjson")
    p=subprocess.run([bin,str(path),"--nat-extension","--string-extension","--axiom-allow-all","--threads","1"],
         stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=360)
    assert p.returncode==0,(case,p.stderr[-1000:])
    matches=[tuple(map(int,m)) for m in re.findall(
      r"SOKO_GROW_CENSUS old_slots=(\d+) new_slots=(\d+) len=(\d+)",p.stderr)]
    row={"case":case,"accepted":True,"grow_count":len(matches),
         "max_old_slots":max([x[0] for x in matches],default=0),
         "max_new_slots":max([x[1] for x in matches],default=0),
         "sum_entries_rehashed":sum(x[2] for x in matches),
         "growth_events":matches[:200],"events_truncated":len(matches)>200}
    record.append(row)
    print("UNFOLD_GROW_CASE="+json.dumps(row),flush=True)
    (out/(case.replace("/","_")+".stderr.txt")).write_text(p.stderr)
bad=sorted((root/"bad").rglob("*.ndjson"))
assert len(bad)==71
p=subprocess.run([bin,str(bad[0]),"--nat-extension","--string-extension","--axiom-allow-all","--threads","1"],
    stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=360)
assert p.returncode!=0,(bad[0],p.returncode)
result={"source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
        "patch":"stderr instrumentation only for OnceCell-keyed PtrMap::grow",
        "measure":"number/capacity of source-attributed map growth events, not instructions",
        "cases":record,"bad_control_nonaccept":True,
        "official_rank_qualified":False}
(out/"grow-census.json").write_text(json.dumps(result,indent=2)+"\n")
