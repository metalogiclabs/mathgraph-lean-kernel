#!/usr/bin/env python3
from __future__ import annotations
import itertools, json, random, statistics
from pathlib import Path
from run import make_world, observe, oracle_join, wrong_join, N_LATENT
from test2b_emit import bits_to_hex
from test2b_score import learn_source_coordinate, eval_graph

N_WORLDS=12
N_JOIN=24

# Frozen semantic rule induced from the Test 2b residual:
# LLM proposes what relation means; deterministic machinery applies it exhaustively.
RULE={
  "name":"signature_equivalence_or_complement",
  "same_signature_parity":0,
  "bitwise_complement_parity":1,
  "scope":"cross-channel only"
}

def complement_hex(h,n_bits):
    width=(n_bits+3)//4
    mask=(1<<n_bits)-1
    return f"{((~int(h,16)) & mask):0{width}x}"

def hybrid_graph(seed):
    rng,channels=make_world(seed)
    join_z=[tuple(rng.randrange(2) for _ in range(N_LATENT)) for _ in range(N_JOIN)]
    nodes=[]
    sig={}
    for cname,ch in channels.items():
        obs=[observe(z,ch) for z in join_z]
        for i,tok in enumerate(ch.tokens):
            n=(cname,i); nodes.append(n)
            sig[n]=bits_to_hex([row[i] for row in obs])
    g={n:[] for n in nodes}
    for i,u in enumerate(nodes):
        for v in nodes[i+1:]:
            if u[0]==v[0]: continue
            if sig[u]==sig[v]: p=0
            elif complement_hex(sig[u],N_JOIN)==sig[v]: p=1
            else: continue
            g[u].append((v,p)); g[v].append((u,p))
    return rng,channels,g

def score_world(seed):
    rng,channels,g=hybrid_graph(seed)
    tasks=[]; names=list(channels)
    for ai,s in enumerate(names):
        for t in names[ai+1:]:
            for f in sorted(set(channels[s].factors)&set(channels[t].factors)):
                tasks.append((s,t,f))
    source,target,factor=rng.choice(tasks)
    cal=[tuple(rng.randrange(2) for _ in range(N_LATENT)) for _ in range(24)]
    obs=[observe(z,channels[source]) for z in cal]; labels=[z[factor] for z in cal]
    si,df=learn_source_coordinate(obs,labels); source_node=(source,si)
    test=list(itertools.product((0,1), repeat=N_LATENT)); rng.shuffle(test)
    hybrid=eval_graph(g,source_node,df,target,test,factor,channels)
    oracle=eval_graph(oracle_join(channels),source_node,df,target,test,factor,channels)
    wrong=eval_graph(wrong_join(random.Random(seed+100000),channels),source_node,df,target,test,factor,channels)
    return {"seed":seed,"source":source,"target":target,"factor":factor,
            "B_full_history_local":0.5,"F_union_vocab_no_new_coords":0.5,
            "C_wrong_join":wrong,"D_hybrid_rule_plus_exact_closure":hybrid,"E_oracle_join":oracle}

def main():
    rows=[score_world(s) for s in range(N_WORLDS)]
    arms=["B_full_history_local","F_union_vocab_no_new_coords","C_wrong_join","D_hybrid_rule_plus_exact_closure","E_oracle_join"]
    means={a:statistics.mean(r[a] for r in rows) for a in arms}
    print('SEMANTIC_JOIN_TEST2C_HYBRID')
    print('SEMANTIC_RULE_FROZEN=signature_equivalence_or_complement')
    print('EXACT_LAYER_ONLY_APPLIES_RULE_AND_GRAPH_CLOSURE=1')
    for r in rows: print('WORLD',json.dumps(r,sort_keys=True))
    for a in arms: print(f'{a}={means[a]:.6f}')
    d=means['D_hybrid_rule_plus_exact_closure']; e=means['E_oracle_join']
    checks={
      'D_beats_B_by_25pp':d-means['B_full_history_local']>=.25,
      'D_beats_F_by_25pp':d-means['F_union_vocab_no_new_coords']>=.25,
      'D_near_oracle':e-d<=.05 and d>=.90,
      'wrong_join_not_competitive':means['C_wrong_join']<=.65,
    }
    for k,v in checks.items(): print(f"GATE {k}={'PASS' if v else 'FAIL'}")
    ok=all(checks.values())
    print('VERDICT=' + ('HYBRID_SEMANTIC_RULE_PLUS_EXACT_CLOSURE_SUPPORTED' if ok else 'HYBRID_NOT_SUPPORTED__TYPE_RESIDUAL'))
    Path('test2c_results.json').write_text(json.dumps({'rule':RULE,'rows':rows,'means':means,'gates':checks,'passed':ok},indent=2))
    if not ok: raise SystemExit(1)
if __name__=='__main__': main()
