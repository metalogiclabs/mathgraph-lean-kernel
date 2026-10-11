#!/usr/bin/env python3
"""Instance-specific hash table growth census, not a performance score."""
import json,pathlib,re,subprocess,sys
root=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
exe="/tmp/soko-grow-census-checker"
focus=["perf/grind-ring-5","perf/magma-list-pair-n7","perf/magma-list-deep-n21","perf/fueled-chain"]
records=[]
for case in focus:
    path=root/"good"/(case+".ndjson")
    p=subprocess.run([exe,str(path),"--nat-extension","--string-extension",
                     "--axiom-allow-all","--threads","1"],
                     stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=360)
    assert p.returncode==0,(case,p.stderr[-1000:])
    events=[(ty,int(old),int(new),int(n)) for ty,old,new,n in re.findall(
       r"SOKO_ALL_GROW_CENSUS ty=(.+?) old_slots=(\d+) new_slots=(\d+) len=(\d+)",p.stderr)]
    bytype={}
    for ty,old,new,n in events:
        entry=bytype.setdefault(ty,{"count":0,"rows_rehashed":0,"max_slots":0})
        entry["count"]+=1
        entry["rows_rehashed"]+=n
        entry["max_slots"]=max(entry["max_slots"],new)
    ordered=sorted(bytype.items(),key=lambda p:-p[1]["rows_rehashed"])
    row={"case":case,"accepted":True,"grow_count":len(events),"types_with_growth":len(bytype),
         "rows_rehashed_total":sum(n for _,_,_,n in events),
         "top_growth_types":dict(ordered[:20]),"types_truncated":len(ordered)>20}
    records.append(row)
    print("ALL_MAP_GROW_CASE="+json.dumps(row),flush=True)
    (out/(case.replace("/","_")+".stderr.txt")).write_text(p.stderr)
bad=sorted((root/"bad").rglob("*.ndjson"))
assert len(bad)==71
b=subprocess.run([exe,str(bad[0]),"--nat-extension","--string-extension","--axiom-allow-all",
                  "--threads","1"],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=360)
assert b.returncode!=0,(bad[0],b.returncode)
result={"pinned_source":"intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d",
        "intervention":"stderr tracing only, no semantic change",
        "metric":"exact growth events by key type, not instruction cost",
        "cases":records,"bad_control_nonaccept":True,"official_rank_qualified":False}
(out/"all-map-grow.json").write_text(json.dumps(result,indent=2)+"\n")
