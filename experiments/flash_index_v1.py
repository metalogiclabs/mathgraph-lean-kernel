#!/usr/bin/env python3
import json, sys
from collections import defaultdict, deque
from pathlib import Path

SCHEMA="mathgraph.flash.impact-index.v1"

def build(manifest,evidence):
    caps={c["id"]:c for c in manifest["capabilities"]}
    reverse=defaultdict(set)
    for cid,c in caps.items():
        for dep in c.get("dependencies",[]):
            assert dep in caps, (cid,dep)
            reverse[dep].add(cid)

    def downstream(seeds):
        seen=set(seeds)
        q=deque(seeds)
        while q:
            x=q.popleft()
            for y in reverse.get(x,()):
                if y not in seen:
                    seen.add(y); q.append(y)
        return seen

    direct=defaultdict(set)
    for cid,c in caps.items():
        for fam in c.get("evidence_families",[]):
            direct[fam].add(cid)

    family_index={}
    for fam,seeds in direct.items():
        family_index[fam]={
            "direct":sorted(seeds),
            "affected":sorted(downstream(seeds)),
        }

    event_index={}
    for e in evidence["events"]:
        fam=e.get("family")
        event_index[e["id"]]={
            "family":fam,
            "affected_capabilities":family_index.get(fam,{}).get("affected",[]),
        }

    rejected=defaultdict(list)
    for e in evidence["events"]:
        if e.get("action")=="reject" and e.get("family"):
            rejected[e["family"]].append(e["id"])
    killed={fam:ids for fam,ids in rejected.items() if len(ids)>=2}

    return {
        "schema":SCHEMA,
        "families":dict(sorted(family_index.items())),
        "events":event_index,
        "reverse_dependencies":{k:sorted(v) for k,v in sorted(reverse.items())},
        "killed_families":dict(sorted(killed.items())),
    }

def impacted(index,family):
    return index["families"].get(family,{}).get("affected",[])

def main():
    if len(sys.argv)!=4:
        raise SystemExit("usage: flash_index_v1.py manifest.json evidence.json out.json")
    mp,ep,op=map(Path,sys.argv[1:])
    idx=build(json.loads(mp.read_text()),json.loads(ep.read_text()))
    op.write_text(json.dumps(idx,indent=2,sort_keys=True)+"\n")
    print("FLASH_IMPACT_INDEX_PASS")
    for fam in sorted(idx["families"]):
        print(f"{fam}\t{','.join(idx['families'][fam]['affected'])}")

if __name__=="__main__":
    main()
