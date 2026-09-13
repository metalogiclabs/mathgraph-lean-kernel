#!/usr/bin/env python3
import json, re, sys
from collections import defaultdict
from pathlib import Path

RE=re.compile(r"V116_CELL k=(\S+) root=(\S+) mask=(\S+) calls=(\d+) hits=(\d+) success=(\d+) fail=(\d+) selected_sum=(\d+) saved_sum=(\d+) same_env=(\d+)")

def parse(path):
    out=[]
    for line in Path(path).read_text(errors="replace").splitlines():
        m=RE.search(line)
        if not m: continue
        k,root,mask,*nums=m.groups()
        calls,hits,success,fail,selected,saved,same=map(int,nums)
        cold=max(1,calls-hits)
        out.append(dict(k=k,root=root,mask=mask,calls=calls,hits=hits,success=success,fail=fail,
                        selected_sum=selected,saved_sum=saved,same_env=same,
                        hit_rate=hits/calls,
                        success_rate=success/cold,
                        selected_per_success=selected/max(1,success),
                        saved_per_success=saved/max(1,success)))
    return out

def main():
    if len(sys.argv)<4: raise SystemExit("usage: analyze_v116.py OUT_JSON workload=file ...")
    target=Path(sys.argv[1]); rows={}
    for spec in sys.argv[2:]:
        w,p=spec.split("=",1); rows[w]=parse(p)
    keys=set()
    maps={}
    for w,rs in rows.items():
        maps[w]={(r["k"],r["root"],r["mask"]):r for r in rs}; keys|=set(maps[w])
    report=[]
    for key in sorted(keys):
        item={"cell":{"k":key[0],"root":key[1],"mask":key[2]}}
        for w in rows:
            item[w]=maps[w].get(key)
        report.append(item)
    target.write_text(json.dumps({"cells":report},indent=2,sort_keys=True))
    print("V116_ANALYSIS_BEGIN")
    for item in sorted(report,key=lambda x:-(sum((x[w] or {}).get("calls",0) for w in rows))):
        bits=[]
        for w in rows:
            r=item[w]
            if r:
                bits.append(f"{w}:calls={r['calls']},hit={r['hit_rate']:.3f},save={r['saved_per_success']:.1f},sel={r['selected_per_success']:.1f},fail={r['fail']}")
        print("V116_COMPARE",item["cell"]," | ".join(bits))
    print("V116_ANALYSIS_END")

if __name__=="__main__": main()
