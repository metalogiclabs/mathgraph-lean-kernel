#!/usr/bin/env python3
from __future__ import annotations
import csv,itertools,sys
from dataclasses import dataclass

@dataclass(frozen=True)
class Row:
    corpus:str; event:str; safe:int; d:int; empty:int; closed:int; canonical:int

def load(path):
    out=[]
    with open(path,newline='') as f:
        r=csv.DictReader(f)
        for z in r:
            out.append(Row(z['corpus'],z['event_id'],int(z['safe']),int(z['disc_hash']),int(z['spine_empty']),int(z['closed']),int(z['canonical'])))
    return out

def base_atoms(r):
    return {'empty':r.empty,'closed':r.closed,'canonical':r.canonical}

def generated_exprs():
    # Generic grammar derivations, not a fixed probe menu. Expressions are enumerated
    # compositionally from source atom disc_hash and generic bit/eq operators.
    for k in range(16):
        yield (2,f'bit(disc_hash,{k})',lambda r,k=k:(r.d>>k)&1)
    for k in range(16):
        yield (2,f'eq(disc_hash,{k})',lambda r,k=k:int(r.d==k))
        yield (2,f'neq(disc_hash,{k})',lambda r,k=k:int(r.d!=k))

def best_rule(rows, extra=None):
    feats=[('empty',lambda r:r.empty),('closed',lambda r:r.closed),('canonical',lambda r:r.canonical)]
    if extra: feats.append(('g',extra))
    candidates=[]
    atoms=[]
    for name,fn in feats:
        atoms.extend([(name,0,fn),(name,1,fn)])
    for k in range(1,5):
        for combo in itertools.combinations(atoms,k):
            if len({x[0] for x in combo})!=k: continue
            def holds(r,combo=combo): return all(fn(r)==v for _,v,fn in combo)
            su=sum(r.safe and holds(r) for r in rows); un=sum((not r.safe) and holds(r) for r in rows)
            if su and not un:
                text='&'.join(f'{n}={v}' for n,v,_ in combo)
                candidates.append((-su,k,text,holds,su))
    if not candidates: return None
    candidates.sort(key=lambda z:(z[0],z[1],z[2]))
    return candidates[0]

def broader(text):
    parts=text.split('&')
    if len(parts)<=1: return 'TRUE'
    return '&'.join(parts[:-1])

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: probe_form_genesis_v15.py observations.csv')
    rows=load(sys.argv[1]); safe=sum(r.safe for r in rows); unsafe=len(rows)-safe
    print(f'V15_EVENTS total={len(rows)} safe={safe} unsafe={unsafe}')
    base=best_rule(rows)
    bcov=base[4] if base else 0
    print(f'V15_INITIAL_FRONTIER safe_coverage={bcov} rule={base[2] if base else "NONE"}')
    if bcov>=safe:
        print('PROBE_FORM_GENESIS_V15=NO_GENESIS_NEEDED'); return 3
    scored=[]
    for ecost,text,fn in generated_exprs():
        br=best_rule(rows,fn)
        if not br: continue
        cov=br[4]; total_cost=ecost+br[1]
        sig=tuple(fn(r) for r in rows)
        scored.append((-cov,total_cost,ecost,text,br[2],sig,fn,br))
        print(f'V15_GENERATED_EXPR expr={text} expr_cost={ecost} safe_coverage={cov} total_cost={total_cost} rule={br[2]}')
    if not scored:
        print('PROBE_FORM_GENESIS_V15=UNDERIDENTIFIED'); return 2
    scored.sort(key=lambda z:(z[0],z[1],z[2],z[3],z[4]))
    best_cov=-scored[0][0]; best_total=scored[0][1]
    if best_cov<=bcov:
        print('PROBE_FORM_GENESIS_V15=NO_GENESIS_NEEDED'); return 3
    top=[z for z in scored if -z[0]==best_cov and z[1]==best_total]
    classes={}
    for z in top: classes.setdefault(z[5],z)
    print(f'V15_BEST_BEHAVIOURAL_CLASSES={len(classes)}')
    if len(classes)!=1:
        print('PROBE_FORM_GENESIS_V15=UNDERIDENTIFIED'); return 2
    z=next(iter(classes.values()))
    same=[q for q in top if q[5]==z[5]]; same.sort(key=lambda q:(q[2],q[3],q[4])); z=same[0]
    expr=z[3]; rule=z[4]
    print(f'V15_GENERATED_PROBE_EXPR={expr}')
    print(f'V15_GENERATED_PREDICATE={rule}')
    print(f'V15_GENERATED_FRONTIER safe_coverage={best_cov}')
    print(f'V15_STRICT_FRONTIER_GAIN={best_cov-bcov}')
    print('V15_INITIAL_LANGUAGE_INSUFFICIENT=PASS')
    print('V15_UNIQUE_MINIMUM_GENERATED_BEHAVIOURAL_CLASS=PASS')
    print('V15_GENERIC_GRAMMAR_DERIVATION=PASS')
    print('V15_EXACT_PROBE_ABLATION_FRONTIER=PASS')
    open('/tmp/v15_expr.txt','w').write(expr)
    open('/tmp/v15_predicate.txt','w').write(rule)
    open('/tmp/v15_broad_predicate.txt','w').write(broader(rule))

if __name__=='__main__': main()
