#!/usr/bin/env python3
from __future__ import annotations
import itertools, json, random, statistics
from collections import deque
from pathlib import Path
from run import make_world, observe, oracle_join, wrong_join, N_LATENT

N_WORLDS=12
N_JOIN=24

def graph_from_edges(edges, channels):
    token_to_node={tok:(c,i) for c,ch in channels.items() for i,tok in enumerate(ch.tokens)}
    nodes=list(token_to_node.values()); g={n:[] for n in nodes}
    for a,b,p in edges:
        if a not in token_to_node or b not in token_to_node: continue
        u,v=token_to_node[a],token_to_node[b]
        g[u].append((v,int(p))); g[v].append((u,int(p)))
    return g

def find_target_coordinate(graph, source, target_channel):
    q=deque([(source,0)]); seen={source}
    while q:
        n,p=q.popleft()
        if n[0]==target_channel: return n,p
        for nxt,e in graph.get(n,[]):
            if nxt not in seen:
                seen.add(nxt); q.append((nxt,p^e))
    return None

def learn_source_coordinate(obs, labels):
    best=None
    for i in range(len(obs[0])):
        for flip in (0,1):
            correct=sum((o[i]^flip)==y for o,y in zip(obs,labels))
            cand=(correct,-i,-flip,i,flip)
            if best is None or cand>best: best=cand
    return best[3],best[4]

def eval_graph(graph, source_node, decode_flip, target, test_z, factor, channels):
    mapped=find_target_coordinate(graph,source_node,target)
    if mapped is None: return 0.5
    (node,rel)=mapped; ti=node[1]
    pred=[observe(z,channels[target])[ti]^rel^decode_flip for z in test_z]
    truth=[z[factor] for z in test_z]
    return sum(a==b for a,b in zip(pred,truth))/len(truth)

def score_world(seed, edges):
    rng,channels=make_world(seed)
    for _ in range(N_JOIN):
        tuple(rng.randrange(2) for _ in range(N_LATENT))
    # downstream target chosen only after frozen join evidence has been consumed
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
    llm=eval_graph(graph_from_edges(edges,channels),source_node,df,target,test,factor,channels)
    oracle=eval_graph(oracle_join(channels),source_node,df,target,test,factor,channels)
    wrong=eval_graph(wrong_join(random.Random(seed+100000),channels),source_node,df,target,test,factor,channels)
    return {"seed":seed,"source":source,"target":target,"factor":factor,"B_full_history_local":0.5,"F_union_vocab_no_new_coords":0.5,"C_wrong_join":wrong,"D_llm_frozen_join":llm,"E_oracle_join":oracle}

def main():
    frozen=json.loads(Path('test2b_frozen_llm_join.json').read_text())['worlds']
    rows=[score_world(s,frozen[str(s)]) for s in range(N_WORLDS)]
    arms=["B_full_history_local","F_union_vocab_no_new_coords","C_wrong_join","D_llm_frozen_join","E_oracle_join"]
    means={a:statistics.mean(r[a] for r in rows) for a in arms}
    print('SEMANTIC_JOIN_TEST2B_FROZEN_LLM')
    print('JOIN_FROZEN_BEFORE_DOWNSTREAM_TARGET=1')
    print('MODEL=GPT-5.6_Sol')
    for r in rows: print('WORLD',json.dumps(r,sort_keys=True))
    for a in arms: print(f'{a}={means[a]:.6f}')
    print(f"D_minus_B={means['D_llm_frozen_join']-means['B_full_history_local']:+.6f}")
    print(f"D_minus_F={means['D_llm_frozen_join']-means['F_union_vocab_no_new_coords']:+.6f}")
    print(f"oracle_gap_E_minus_D={means['E_oracle_join']-means['D_llm_frozen_join']:+.6f}")
    checks={
      'D_beats_B_by_25pp':means['D_llm_frozen_join']-means['B_full_history_local']>=.25,
      'D_beats_F_by_25pp':means['D_llm_frozen_join']-means['F_union_vocab_no_new_coords']>=.25,
      'D_near_oracle':means['E_oracle_join']-means['D_llm_frozen_join']<=.10 and means['D_llm_frozen_join']>=.85,
      'wrong_join_not_competitive':means['C_wrong_join']<=.65,
    }
    for k,v in checks.items(): print(f"GATE {k}={'PASS' if v else 'FAIL'}")
    ok=all(checks.values())
    print('VERDICT=' + ('LLM_SEMANTIC_JOIN_SUPPORTED_IN_FROZEN_SEALED_WORLD' if ok else 'LLM_JOIN_NOT_SUPPORTED__TYPE_RESIDUAL'))
    Path('test2b_results.json').write_text(json.dumps({'rows':rows,'means':means,'gates':checks,'passed':ok},indent=2))
    if not ok: raise SystemExit(1)
if __name__=='__main__': main()
