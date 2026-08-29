#!/usr/bin/env python3
from __future__ import annotations
import json,re,sys
from pathlib import Path

if len(sys.argv) != 9:
    raise SystemExit('usage: select_v40 V39_SELECTION OUT LOCAL_1M LOCAL_2M SHARED_1M SHARED_2M GATED_1M GATED_2M')

sel=json.loads(Path(sys.argv[1]).read_text())
outp=Path(sys.argv[2])
paths=sys.argv[3:]

def summary(p:str)->int:
    m=re.search(r'^summary:\s+(\d+)',Path(p).read_text(errors='replace'),re.M)
    if not m: raise SystemExit('missing callgrind summary '+p)
    return int(m.group(1))

modes=('local','shared','gated')
cost={}
for i,mode in enumerate(modes):
    a=summary(paths[2*i]); b=summary(paths[2*i+1])
    if b <= a: raise SystemExit('nonpositive acquisition continuation cost for '+mode)
    cost[mode]=b-a

# Frozen rule: among semantically admissible implementations, retain the least
# acquisition-continuation instruction cost. Ties prefer less architectural
# commitment: local, then shared, then gated.
order={'local':0,'shared':1,'gated':2}
winner=min(modes,key=lambda m:(cost[m],order[m]))
res={
  'schema':'msi.earned-memory-policy.selector.v40',
  'selection_uses_heldout':False,
  'capability':sel['winner_materializer'],
  'applicability':sel['winner_applicability_materializer'],
  'policy_candidates':[{ 'mode':m, 'acquisition_continuation_instructions':cost[m]} for m in modes],
  'winner_policy':winner,
  'policy_rule':'minimum deterministic acquisition-continuation instruction cost among semantically exact local/shared/gated arms; tie-break local<shared<gated',
}
outp.write_text(json.dumps(res,indent=2,sort_keys=True))
print('MSI_V40_POLICY',json.dumps(res,sort_keys=True))
