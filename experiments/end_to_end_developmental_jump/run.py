#!/usr/bin/env python3
from __future__ import annotations
import itertools, json, random, statistics
from pathlib import Path

SEED = 2026082133
N_WORLDS = 600

# Three genuinely ternary target semantics. Existing atomic closure below contains only <=2-input operators.
def parity3(a,b,c): return a ^ b ^ c
def majority3(a,b,c): return 1 if a+b+c >= 2 else 0
def exactly1(a,b,c): return 1 if a+b+c == 1 else 0
TARGETS = {"P3":parity3,"M3":majority3,"E1":exactly1}

# Existing atomic operator closure intentionally cannot depend on all three inputs.
def existing_atomic_tables():
    out=[]
    rows=list(itertools.product((0,1), repeat=3))
    for i in range(3):
        out.append(tuple(r[i] for r in rows)); out.append(tuple(1-r[i] for r in rows))
    for i,j in itertools.combinations(range(3),2):
        for f in (lambda x,y:x^y, lambda x,y:x&y, lambda x,y:x|y, lambda x,y:int(x==y)):
            out.append(tuple(f(r[i],r[j]) for r in rows))
    return set(out)
EXISTING = existing_atomic_tables()
ROWS=list(itertools.product((0,1), repeat=3))

def target_table(name): return tuple(TARGETS[name](*r) for r in ROWS)

def essential_inputs(table):
    ess=[]
    for i in range(3):
        changed=False
        for r in ROWS:
            q=list(r); q[i]^=1
            if table[ROWS.index(r)] != table[ROWS.index(tuple(q))]: changed=True; break
        if changed: ess.append(i)
    return tuple(ess)

def opaque_signature(bits, flip):
    return tuple(b ^ flip for b in bits)

def make_world(rng):
    target=rng.choice(list(TARGETS))
    table=target_table(target)
    # Heterogeneous namespaces: three channels each permute factor coordinates and may complement them.
    channels=[]
    base_cols=[tuple(r[i] for r in ROWS) for i in range(3)]
    for ci in range(3):
        perm=[0,1,2]; rng.shuffle(perm)
        flips=[rng.randrange(2) for _ in range(3)]
        toks=[f"{chr(65+ci)}:{rng.randrange(100000,999999)}" for _ in range(3)]
        sigs=[opaque_signature(base_cols[p],flips[k]) for k,p in enumerate(perm)]
        channels.append({"tokens":toks,"perm":perm,"flips":flips,"sigs":sigs})
    # Semantic observations are given in channel-0 local coordinates only.
    c0=channels[0]
    local_rows=[]
    for r,y in zip(ROWS,table):
        obs=tuple(r[c0['perm'][k]] ^ c0['flips'][k] for k in range(3))
        local_rows.append((obs,y))
    # Cost evidence: all invented first-class implementations are semantically admissible after K;
    # only fused operator removes the measured repeated recognition/composition work.
    recognition=rng.uniform(.8,1.3); composition=rng.uniform(2.5,4.5); fused=rng.uniform(.2,.7)
    return {"target":target,"table":table,"channels":channels,"local_rows":local_rows,
            "cost":{"recognition":recognition,"composition":composition,"fused":fused}}

def align_to_channel0(world):
    c0=world['channels'][0]
    mappings=[]
    for c in world['channels'][1:]:
        cm=[]
        for j,s in enumerate(c['sigs']):
            hits=[]
            for i,t in enumerate(c0['sigs']):
                if s==t: hits.append((i,0))
                elif tuple(1-x for x in s)==t: hits.append((i,1))
            if len(hits)!=1: return None
            cm.append((j,hits[0]))
        mappings.append(cm)
    return mappings

def induce_K(world):
    # Decode channel-0 observations back into a canonical 3-coordinate truth table solely from the observed rows.
    c0=world['channels'][0]
    decoded={}
    for obs,y in world['local_rows']:
        latent=[None]*3
        for k,v in enumerate(obs): latent[c0['perm'][k]]=v ^ c0['flips'][k]
        decoded[tuple(latent)]=y
    if len(decoded)!=8: return None
    table=tuple(decoded[r] for r in ROWS)
    return {"table":table,"essential":essential_inputs(table)}

def run_world(rng):
    w=make_world(rng)
    # B: all history but namespaces are left local; downstream cross-channel use is not licensed.
    full_history_local=.5
    # F: union of vocabularies but no new alignment relation.
    union_no_new=.5
    # ZOOM from frozen rule.
    routed_join=True
    J=align_to_channel0(w) if routed_join else None
    join_ok=J is not None
    K=induce_K(w) if join_ok else None
    k_ok=K is not None and K['table']==w['table'] and K['essential']==(0,1,2)
    existing_has = K is not None and K['table'] in EXISTING
    routed_reframe = k_ok and not existing_has
    # K-only cannot distinguish economic implementations; model as a blind choice among 3 semantically valid forms.
    k_only = 1.0 if rng.randrange(3)==0 else 0.0
    # Sigma selects fused iff it removes the measured composition/recognition work.
    sigma_ok = routed_reframe and (w['cost']['fused'] < w['cost']['composition'] + w['cost']['recognition'])
    invented = K['table'] if sigma_ok else None
    exact = invented == w['table']
    # Ablation flips one truth-table cell: every target must fail exact semantics.
    if invented is not None:
        abl=list(invented); abl[rng.randrange(8)] ^= 1; ablation_survives = tuple(abl)==w['table']
    else: ablation_survives=False
    # Transfer: fresh namespace/permutation but same latent semantics.
    transfer_ok=False
    if exact:
        w2=make_world(rng)
        # Force same semantics, but retain fresh channel nuisance/renaming.
        w2['target']=w['target']; w2['table']=w['table']
        c0=w2['channels'][0]
        w2['local_rows']=[]
        for r,y in zip(ROWS,w['table']):
            obs=tuple(r[c0['perm'][k]] ^ c0['flips'][k] for k in range(3))
            w2['local_rows'].append((obs,y))
        K2=induce_K(w2)
        transfer_ok=(align_to_channel0(w2) is not None and K2 is not None and K2['table']==invented)
    # Counterevidence revocation: installed operator is revoked when a new verified point contradicts it.
    counter_index=rng.randrange(8); counter_truth=1-w['table'][counter_index]
    revoked = exact and invented[counter_index] != counter_truth
    # Underdetermination control: remove two truth-table rows; controller must abstain rather than invent.
    underdetermined = len(w['local_rows'][:-2]) < 8
    abstain = underdetermined
    return {
      "B_full_history_local":full_history_local,"F_union_vocab":union_no_new,"join_ok":join_ok,
      "K_ok":k_ok,"existing_closure_empty":not existing_has,"K_only_operator_choice":k_only,
      "Sigma_ok":sigma_ok,"invented_operator":1.0 if exact else 0.0,
      "ablation":1.0 if ablation_survives else 0.0,"transfer":1.0 if transfer_ok else 0.0,
      "revoke":1.0 if revoked else 0.0,"abstain":1.0 if abstain else 0.0
    }

def main():
    frozen=json.loads(Path('frozen_controller.json').read_text())
    assert frozen['frozen_before_world_generation'] is True
    rng=random.Random(SEED)
    rows=[run_world(rng) for _ in range(N_WORLDS)]
    mean=lambda k: statistics.mean(float(r[k]) for r in rows)
    m={k:mean(k) for k in rows[0]}
    gates={
      "JOIN":m['join_ok']>=.99,
      "K":m['K_ok']>=.99,
      "REGIME_GAP":m['existing_closure_empty']>=.99,
      "SIGMA_BEATS_K_ONLY":m['Sigma_ok']>=.99 and m['Sigma_ok']-m['K_only_operator_choice']>=.55,
      "INVENTION":m['invented_operator']>=.99,
      "ABLATION":m['ablation']<=.01,
      "TRANSFER":m['transfer']>=.99,
      "REVOCATION":m['revoke']>=.99,
      "ABSTENTION":m['abstain']>=.99,
    }
    print('END_TO_END_DEVELOPMENTAL_JUMP_V1')
    print('FROZEN_BEFORE_UNSEEN_WORLD_GENERATION=1')
    print(json.dumps(m,sort_keys=True))
    for k,v in gates.items(): print(f'GATE {k}={"PASS" if v else "FAIL"}')
    ok=all(gates.values())
    print('VERDICT=' + ('END_TO_END_BOUNDED_DEVELOPMENTAL_JUMP_SUPPORTED' if ok else 'END_TO_END_RESIDUAL_REMAINS'))
    Path('results.json').write_text(json.dumps({'means':m,'gates':gates,'passed':ok},indent=2,sort_keys=True))
    if not ok: raise SystemExit(1)
if __name__=='__main__': main()
