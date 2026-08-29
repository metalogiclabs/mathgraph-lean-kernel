#!/usr/bin/env python3
from __future__ import annotations
import json,re,sys
from collections import defaultdict
from pathlib import Path

V36 = re.compile(r"MSI_V36 total=(?P<total>\d+) sort_ensure=(?P<sort_ensure>\d+) sort_ensure_pre=(?P<sort_ensure_pre>\d+) app_pi=(?P<app_pi>\d+) app_pi_pre=(?P<app_pi_pre>\d+) app_sort_pair=(?P<app_sort_pair>\d+) let_sort_pair=(?P<let_sort_pair>\d+) proj_ind=(?P<proj_ind>\d+) proj_ind_pre=(?P<proj_ind_pre>\d+)")
APP = re.compile(r"MSI_V39_APP pre=(p\d+) unchanged=(\d)")
MAP = {"p0":"bvar","p1":"axiom","p2":"ctor","p3":"recursor","p4":"quotconst","p5":"inductive","p6":"nonrigid"}

def main():
    if len(sys.argv)!=4: raise SystemExit('usage: selector V36_LOG APP_LOG OUT')
    t1=Path(sys.argv[1]).read_text(errors='replace')
    ms=list(V36.finditer(t1))
    if not ms: raise SystemExit('no V36 trace')
    x={k:int(v) for k,v in ms[-1].groupdict().items()}
    caps=[
      {"id":"c0","materializer":"sort","consumer_sites":sum(int(v>0) for v in (x['sort_ensure'],x['app_sort_pair'],x['let_sort_pair'])),"established":x['sort_ensure_pre']+x['app_sort_pair']+x['let_sort_pair'],"demand":x['sort_ensure']+x['app_sort_pair']+x['let_sort_pair']},
      {"id":"c1","materializer":"pi","consumer_sites":int(x['app_pi']>0),"established":x['app_pi_pre'],"demand":x['app_pi']},
      {"id":"c2","materializer":"inductive","consumer_sites":int(x['proj_ind']>0),"established":x['proj_ind_pre'],"demand":x['proj_ind']},
    ]
    for c in caps: c['preexisting_ratio']=c['established']/c['demand'] if c['demand'] else 0.0
    caps_ranked=sorted([c for c in caps if c['established'] and c['demand']],key=lambda c:(-c['consumer_sites'],-c['established'],-c['preexisting_ratio'],c['id']))
    if not caps_ranked: raise SystemExit('no capability candidate')
    cap=caps_ranked[0]

    counts=defaultdict(lambda:[0,0])
    for m in APP.finditer(Path(sys.argv[2]).read_text(errors='replace')):
        k,u=m.group(1),int(m.group(2)); counts[k][0]+=1; counts[k][1]+=u
    preds=[]
    for pid,(n,u) in sorted(counts.items()):
        preds.append({"id":pid,"support":n,"unchanged":u,"invariance_ratio":u/n if n else 0.0})
    # Applicability is earned only by exact invariance on acquisition and nontrivial support.
    eligible=[p for p in preds if p['support']>=32 and p['unchanged']==p['support']]
    if not eligible: raise SystemExit('no exactly invariant applicability class with support >=32')
    pred=sorted(eligible,key=lambda p:(-p['support'],p['id']))[0]

    out={
      "schema":"msi.blind-interface-applicability-genesis.selector.v39",
      "selection_uses_heldout":False,
      "capability_candidates":caps,
      "capability_ranking":[c['id'] for c in caps_ranked],
      "winner_capability_id":cap['id'],
      "winner_materializer":cap['materializer'],
      "applicability_candidates":preds,
      "winner_applicability_id":pred['id'],
      "winner_applicability_materializer":MAP[pred['id']],
      "applicability_rule":"reuse only on acquisition classes with exact force-invariance and support>=32",
    }
    Path(sys.argv[3]).write_text(json.dumps(out,indent=2,sort_keys=True))
    print('MSI_V39_SELECTOR',json.dumps(out,sort_keys=True))

if __name__=='__main__': main()
