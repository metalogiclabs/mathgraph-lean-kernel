#!/usr/bin/env python3
from __future__ import annotations
import csv,itertools,sys
from dataclasses import dataclass

@dataclass(frozen=True)
class Pred:
    lits: tuple[tuple[str,int], ...]
    def holds(self,r,g=None):
        for n,v in self.lits:
            if n=='empty': q=r['empty']
            elif n=='closed': q=r['closed']
            elif n=='canonical': q=r['canonical']
            elif n.startswith('eq'):
                q=int(r['hash']==int(n[2:]))
            elif n.startswith('neq'):
                q=int(r['hash']!=int(n[3:]))
            elif n=='g': q=int(g)
            else: raise ValueError(n)
            if q!=v: return False
        return True
    @property
    def cost(self): return len(self.lits)
    def encode(self): return '&'.join(f'{n}={v}' for n,v in self.lits) or 'TRUE'

def load(path):
    out=[]
    with open(path,newline='') as f:
        rd=csv.DictReader(f)
        for x in rd:
            out.append({'corpus':x['corpus'],'event':int(x['event_id']),'safe':int(x['safe']),
                        'hash':int(x['disc_hash']),'empty':int(x['spine_empty']),
                        'closed':int(x['closed']),'canonical':int(x['canonical'])})
    return out

def pred_space(atoms,max_lits=2):
    yield Pred(tuple())
    for k in range(1,max_lits+1):
        for names in itertools.combinations(atoms,k):
            for vals in itertools.product((0,1), repeat=k):
                yield Pred(tuple(zip(names,vals)))

def best(rows,atoms,gvals=None,max_lits=2):
    scored=[]
    for p in pred_space(atoms,max_lits):
        su=un=0
        sig=[]
        for i,r in enumerate(rows):
            h=p.holds(r,None if gvals is None else gvals[i]); sig.append(h)
            if h:
                if r['safe']: su+=1
                else: un+=1
        if su and un==0: scored.append((-su,p.cost,p.encode(),p,tuple(sig)))
    if not scored: return None
    scored.sort(key=lambda z:(z[0],z[1],z[2]))
    return scored[0]

def gen(schema,h,k):
    if schema=='shift_mask': return (h>>k)&1
    if schema=='shift_mod2': return (h>>k)%2
    if schema=='mask_nonzero': return int((h & (1<<k)) != 0)
    raise ValueError(schema)

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: operator_alphabet_genesis_v16.py observations.csv')
    rows=load(sys.argv[1]); safe=sum(r['safe'] for r in rows); unsafe=len(rows)-safe
    print(f'V16_EVENTS total={len(rows)} safe={safe} unsafe={unsafe}')
    if not safe or not unsafe:
        print('OPERATOR_ALPHABET_GENESIS_V16=UNDERIDENTIFIED'); return 2

    initial_atoms=['empty','closed','canonical']+[f'eq{k}' for k in range(16)]+[f'neq{k}' for k in range(16)]
    ib=best(rows,initial_atoms,None,2)
    init_cov=-ib[0] if ib else 0
    init_rule=ib[2] if ib else 'NONE'
    print(f'V16_INITIAL_FRONTIER safe_coverage={init_cov} rule={init_rule}')
    if init_cov==safe:
        print('OPERATOR_ALPHABET_GENESIS_V16=NO_GENESIS_NEEDED'); return 3

    schemas=('shift_mask','shift_mod2','mask_nonzero')
    choices=[]
    for schema in schemas:
        for k in range(16):
            gv=[gen(schema,r['hash'],k) for r in rows]
            b=best(rows,['empty','closed','canonical','g'],gv,2)
            if not b: continue
            cov=-b[0]; pcost=b[1]; opcost=2; total=opcost+pcost
            gsig=tuple(gv)
            print(f'V16_OPERATOR_CANDIDATE schema={schema} k={k} safe_coverage={cov} total_cost={total} rule={b[2]}')
            choices.append((-cov,total,schema,k,b[2],b[3],gsig,cov))
    if not choices:
        print('OPERATOR_ALPHABET_GENESIS_V16=UNDERIDENTIFIED'); return 2
    choices.sort(key=lambda z:(z[0],z[1],z[2],z[3],z[4]))
    best_cov=-choices[0][0]; best_cost=choices[0][1]
    if best_cov<=init_cov:
        print(f'V16_NO_STRICT_OPERATOR_GAIN initial={init_cov} expanded={best_cov}')
        print('OPERATOR_ALPHABET_GENESIS_V16=FALSIFIED'); return 4

    top=[z for z in choices if -z[0]==best_cov and z[1]==best_cost]
    beh={}
    for z in top: beh.setdefault((z[6], tuple(z[5].holds(r,z[6][i]) for i,r in enumerate(rows))),z)
    print(f'V16_BEST_BEHAVIOURAL_CLASSES={len(beh)}')
    if len(beh)!=1:
        for z in list(beh.values())[:20]: print(f'V16_AMBIGUOUS_OPERATOR schema={z[2]} k={z[3]} rule={z[4]}')
        print('OPERATOR_ALPHABET_GENESIS_V16=UNDERIDENTIFIED'); return 2

    clskey,z=next(iter(beh.items()))
    equivalents=[q for q in top if (q[6],tuple(q[5].holds(r,q[6][i]) for i,r in enumerate(rows)))==clskey]
    equivalents.sort(key=lambda q:(q[2],q[3],q[4]))
    z=equivalents[0]
    schema,k,rule=z[2],z[3],z[4]
    expr=f'{schema}(disc_hash,{k})'
    print(f'V16_GENERATED_OPERATOR_SCHEMA={schema}')
    print(f'V16_GENERATED_OPERATOR_EXPR={expr}')
    print(f'V16_GENERATED_PREDICATE={rule}')
    print(f'V16_GENERATED_FRONTIER safe_coverage={best_cov}')
    print(f'V16_STRICT_FRONTIER_GAIN={best_cov-init_cov}')
    print('V16_INITIAL_LANGUAGE_INSUFFICIENT=PASS')
    print('V16_UNIQUE_BEST_OPERATOR_BEHAVIOURAL_CLASS=PASS')
    print('V16_EXACT_OPERATOR_ABLATION_FRONTIER=PASS')
    open('/tmp/v16_expr.txt','w').write(expr)
    open('/tmp/v16_predicate.txt','w').write(rule)
    open('/tmp/v16_broad_predicate.txt','w').write('TRUE')

if __name__=='__main__': main()
