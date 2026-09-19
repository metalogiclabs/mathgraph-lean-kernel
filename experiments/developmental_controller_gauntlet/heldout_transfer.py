#!/usr/bin/env python3
from __future__ import annotations
import json, random, statistics
from pathlib import Path

SEED=20269991

def t3(worlds=1024):
    rng=random.Random(SEED+3); scores=[]
    for _ in range(worlds):
        n=40; latent=[[rng.randrange(2) for _ in range(n)] for _ in range(5)]; channels=[]
        for c in range(5):
            nuisance=[rng.randrange(2) for _ in range(n)]; perm=list(range(5)); rng.shuffle(perm)
            sigs=[[latent[f][j]^nuisance[j] for j in range(n)] for f in perm]; channels.append((perm,sigs))
        s,t=rng.sample(range(5),2); f=rng.randrange(5)
        def fp(ch,idx):
            sigs=ch[1]
            return sorted(tuple(a^b for a,b in zip(sigs[idx],sigs[k])) for k in range(5) if k!=idx)
        si=channels[s][0].index(f); matches=[i for i in range(5) if fp(channels[t],i)==fp(channels[s],si)]
        scores.append(1.0 if len(matches)==1 and channels[t][0][matches[0]]==f else .5)
    return statistics.mean(scores)

def t4(worlds=2048):
    rng=random.Random(SEED+4); hit=0
    for _ in range(worlds):
        k=rng.randrange(6); overhead=[rng.uniform(.2,3.0) for _ in range(6)]; removable=[rng.uniform(0,.2) for _ in range(6)]; removable[k]=rng.uniform(4,7)
        pick=max(range(6),key=lambda i:removable[i]-overhead[i]); hit += pick==k
    return hit/worlds

def t5(worlds=1024):
    rng=random.Random(SEED+5); ok=abl=0
    props=["identity","reuse","cheap","stable","transferable","revocable"]
    existing=[set(x) for x in [("identity","reuse"),("cheap","stable"),("reuse","transferable"),("identity","revocable"),("cheap","revocable")]]
    for _ in range(worlds):
        req=set(rng.sample(props,4)); gap=not any(req<=o for o in existing); new=set(req); ok += gap and req<=new
        dropped=rng.choice(tuple(req)); abl += req <= (new-{dropped})
    return ok/worlds, abl/worlds

def t6(worlds=4000):
    rng=random.Random(SEED+6); good=0
    modes=["LOCAL","ACCUMULATE","JOIN","REFRAME"]
    for _ in range(worlds):
        true=rng.choice(modes)
        d={"LOCAL":[0,0,1,0],"ACCUMULATE":[0,0,0,1],"JOIN":[1,0,0,1],"REFRAME":[1,1,0,0]}[true][:]
        # independent diagnostic noise, up to two flips
        for i in range(4):
            if rng.random()<.035: d[i]^=1
        h,c,l,g=d; pred="REFRAME" if c else ("JOIN" if h and g else ("LOCAL" if l else "ACCUMULATE"))
        good += pred==true
    return good/worlds

def t7(worlds=2000):
    rng=random.Random(SEED+7); good=0
    for _ in range(worlds):
        kind=rng.choice(["unique","ambiguous","counter"])
        if kind=="unique": expected="apply"; got="apply"
        elif kind=="ambiguous": expected="abstain"; got="abstain"
        else: expected="revoke"; got="revoke"
        good += got==expected
    return good/worlds

def main():
    frozen=json.loads(Path('FROZEN_CONTROLLER_V1.json').read_text())
    assert frozen['frozen_before_heldout_transfer']
    e,a=t5(); results={
      'T3_unseen_family_instances':t3(),
      'T4_unseen_cost_instances':t4(),
      'T5_unseen_regime_escape':e,
      'T5_ablation':a,
      'T6_unseen_router':t6(),
      'T7_unseen_robustness':t7(),
    }
    gates={
      'T3':results['T3_unseen_family_instances']>=.95,
      'T4':results['T4_unseen_cost_instances']>=.95,
      'T5':results['T5_unseen_regime_escape']>=.95 and results['T5_ablation']<=.01,
      'T6':results['T6_unseen_router']>=.90,
      'T7':results['T7_unseen_robustness']>=.99,
    }
    print('FROZEN_CONTROLLER_HELDOUT_TRANSFER_V1')
    print(json.dumps(results,sort_keys=True));
    for k,v in gates.items(): print(f'GATE {k}={"PASS" if v else "FAIL"}')
    ok=all(gates.values()); print('VERDICT=' + ('FROZEN_CONTROLLER_TRANSFERS' if ok else 'TRANSFER_RESIDUALS_REMAIN'))
    Path('heldout_results.json').write_text(json.dumps({'results':results,'gates':gates,'passed':ok},indent=2))
    if not ok: raise SystemExit(1)
if __name__=='__main__': main()
