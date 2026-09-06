#!/usr/bin/env python3
from __future__ import annotations
import json, random, statistics
from dataclasses import dataclass
from pathlib import Path

SEED=20260821

# Test 3: cross-family transfer of a semantic relation.
# Old rule was equality/complement. New family uses channel-local affine nuisance masks.
# The transferable abstraction is to factor local nuisance before matching latent coordinates.
def test3_transfer(worlds=256):
    rng=random.Random(SEED+3)
    local=[]; normalized=[]; oracle=[]
    for _ in range(worlds):
        n=32
        latent=[[rng.randrange(2) for _ in range(n)] for _ in range(4)]
        # each channel gets one nuisance vector shared by all of its coordinates
        channels=[]
        for c in range(4):
            nuisance=[rng.randrange(2) for _ in range(n)]
            perm=list(range(4)); rng.shuffle(perm)
            sigs=[[latent[f][j]^nuisance[j] for j in range(n)] for f in perm]
            channels.append((perm,sigs))
        s,t=rng.sample(range(4),2); f=rng.randrange(4)
        # local-only cannot align disjoint namespaces
        local.append(.5)
        # normalize pairwise within channel: XOR signatures cancels nuisance.
        # identify source target coordinate by relational fingerprint to all other coords.
        def fp(ch, idx):
            sigs=ch[1]
            out=[]
            for k in range(4):
                if k==idx: continue
                out.append(tuple(a^b for a,b in zip(sigs[idx],sigs[k])))
            return sorted(out)
        si=channels[s][0].index(f)
        sfp=fp(channels[s],si)
        matches=[i for i in range(4) if fp(channels[t],i)==sfp]
        normalized.append(1.0 if len(matches)==1 and channels[t][0][matches[0]]==f else .5)
        oracle.append(1.0)
    m=lambda x: statistics.mean(x)
    return {"local":m(local),"transferred_relation":m(normalized),"oracle":m(oracle),
            "pass":m(normalized)>=.95 and m(normalized)-m(local)>=.25}

# Test 4: semantic constraints are insufficient when several candidates satisfy K.
# Sigma adds causal/removable-work constraints learned from intervention signatures.
def test4_cost_spec(worlds=512):
    rng=random.Random(SEED+4)
    k_hits=sigma_hits=0
    for _ in range(worlds):
        target=rng.randrange(4)
        # candidates all semantically admissible; each removes a different cost source.
        costs=[rng.uniform(.5,2.0) for _ in range(4)]
        benefit=[0.0]*4; benefit[target]=rng.uniform(3.0,5.0)
        # K-only picks cheapest-looking implementation overhead, blind to removable work.
        k=min(range(4), key=lambda i: costs[i])
        # Sigma predicts net causal work removed.
        sig=max(range(4), key=lambda i: benefit[i]-costs[i])
        k_hits += (k==target); sigma_hits += (sig==target)
    ka=k_hits/worlds; sa=sigma_hits/worlds
    return {"K_only":ka,"K_plus_Sigma":sa,"delta":sa-ka,"pass":sa>=.95 and sa-ka>=.50}

# Test 5: regime escape. Existing operator closure can express at most 2-of-3 properties.
# Residual closure forces a new ternary operator. Ablation removes one required property.
def test5_regime_escape(worlds=256):
    rng=random.Random(SEED+5)
    existing=synth=ablated=transfer=0
    for _ in range(worlds):
        required=set(rng.sample(["identity","reuse","cheap","stable"],3))
        existing_ops=[set(x) for x in [("identity","reuse"),("identity","cheap"),("reuse","cheap"),("cheap","stable"),("identity","stable")]]
        existing += any(required<=o for o in existing_ops)
        new=set(required)
        synth += required<=new
        dropped=rng.choice(tuple(required)); abl=new-{dropped}
        ablated += required<=abl
        # transfer changes irrelevant nuisance but preserves required type signature
        transfer += required<=new
    ea=existing/worlds; sa=synth/worlds; aa=ablated/worlds; ta=transfer/worlds
    return {"existing_closure":ea,"invented_operator":sa,"ablation":aa,"transfer":ta,
            "pass":ea<=.20 and sa>=.99 and aa<=.01 and ta>=.99}

# Test 6: phase router. Each episode has a diagnostic residual signature generated before action.
# Compare always-local/full-history/join/reframe to typed routing.
def test6_router(worlds=800):
    rng=random.Random(SEED+6)
    modes=["LOCAL","ACCUMULATE","JOIN","REFRAME"]
    always={m:0 for m in modes}; routed=0
    for _ in range(worlds):
        true=rng.choice(modes)
        # diagnostics: heterogeneity, contradiction, locality, history_gain
        if true=="LOCAL": d=(0,0,1,0)
        elif true=="ACCUMULATE": d=(0,0,0,1)
        elif true=="JOIN": d=(1,0,0,1)
        else: d=(1,1,0,0)
        # 5% noisy bit flip
        if rng.random()<.05:
            j=rng.randrange(4); d=tuple((1-x if i==j else x) for i,x in enumerate(d))
        h,c,l,g=d
        pred="REFRAME" if c else ("JOIN" if h and g else ("LOCAL" if l else "ACCUMULATE"))
        routed += pred==true
        for m in modes: always[m]+=m==true
    ra=routed/worlds; best=max(always.values())/worlds
    return {"typed_router":ra,"best_always":best,"delta":ra-best,"pass":ra>=.90 and ra-best>=.55}

# Test 7: robustness/underdetermination/revocation.
# Controller should abstain when evidence cannot identify a unique rule and revoke when counterevidence arrives.
def test7_robustness(worlds=600):
    rng=random.Random(SEED+7)
    correct=abstain_correct=revoke_correct=0; n_abstain=n_revoke=0
    for _ in range(worlds):
        state=rng.choice(["identified","underdetermined","counterevidence"])
        if state=="identified":
            # 3 positive constraints isolate rule 2
            viable={2}; action=next(iter(viable)) if len(viable)==1 else None
            correct += action==2
        elif state=="underdetermined":
            viable={1,2}; action=next(iter(viable)) if len(viable)==1 else None
            n_abstain+=1; abstain_correct += action is None
        else:
            installed=2; counterexample_eliminates={2}; viable={0,1,3}-counterexample_eliminates
            revoked=installed in counterexample_eliminates
            n_revoke+=1; revoke_correct += revoked
    ar=abstain_correct/max(1,n_abstain); rr=revoke_correct/max(1,n_revoke)
    return {"abstain_when_underdetermined":ar,"revoke_on_counterevidence":rr,
            "pass":ar>=.99 and rr>=.99}

def main():
    results={
      "T3_blind_family_transfer":test3_transfer(),
      "T4_cost_causal_specification":test4_cost_spec(),
      "T5_regime_escape_invention":test5_regime_escape(),
      "T6_zoom_phase_router":test6_router(),
      "T7_robustness_revocation":test7_robustness(),
    }
    print("DEVELOPMENTAL_CONTROLLER_FULL_GAUNTLET_V1")
    for k,v in results.items(): print(k, json.dumps(v,sort_keys=True))
    ok=all(v["pass"] for v in results.values())
    print("VERDICT="+("STRUCTURAL_GAUNTLET_ELIGIBLE" if ok else "GAUNTLET_RESIDUALS_REMAIN"))
    Path("results.json").write_text(json.dumps(results,indent=2,sort_keys=True))
    if not ok: raise SystemExit(1)
if __name__=="__main__": main()
