#!/usr/bin/env python3
"""Evaluate a frozen policy on later real records; never refit from held-out data."""
import json, sys
from pathlib import Path
from controller import compile_policy, safe_decision, digest, validate
ROOT=Path(__file__).resolve().parent

def main():
    history=json.loads((ROOT/'history.json').read_text())
    train=[validate(r) for r in history['training']]
    heldout=[validate(r) for r in history['heldout']]
    frozen=json.loads((ROOT/'FROZEN_POLICY.json').read_text())
    assert digest(compile_policy(train))==digest(frozen), 'frozen discovery mismatch'
    rows=[]
    for r in heldout:
        action=safe_decision(frozen,r['state'])
        ablated=safe_decision({'default':'PUSH','clauses':[]},r['state'])
        rows.append({'id':r['id'],'selected':action,'ablation':ablated,'recorded_action':r['action'],
                     'match':action==r['action'],'outcome':r['outcome'],'evidence':r['evidence']})
    observed=[r for r in rows if r['outcome']=='observed']
    result={'policy_sha256':digest(frozen),'training_count':len(train),'heldout_count':len(rows),
            'heldout':rows,'observed_matches':sum(r['match'] for r in observed),
            'observed_count':len(observed),'counterfactual_costs':'UNKNOWN',
            'classification':'RETROSPECTIVE_BOUNDED_TRANSFER','checker_promoted':False}
    assert all(r['match'] for r in observed)
    assert all(r['selected']!='PUSH' for r in rows if r['outcome']=='pending')
    out=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'results.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('POLICY_SHA256='+digest(frozen))
    print('HISTORICAL_OBSERVED_MATCHES=%d/%d'%(result['observed_matches'],result['observed_count']))
    print('HELDOUT_V88_ACTION='+next(r['selected'] for r in rows if r['id']=='v88'))
    print('COUNTERFACTUAL_COSTS=UNKNOWN')
    print('CLASSIFICATION=RETROSPECTIVE_BOUNDED_TRANSFER')
if __name__=='__main__':main()
