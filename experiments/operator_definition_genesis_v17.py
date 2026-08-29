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
            elif n.startswith('eq'): q=int(r['hash']==int(n[2:]))
            elif n.startswith('neq'): q=int(r['hash']!=int(n[3:]))
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
        for x in csv.DictReader(f):
            out.append({'safe':int(x['safe']),'hash':int(x['disc_hash']),'empty':int(x['spine_empty']),
                        'closed':int(x['closed']),'canonical':int(x['canonical'])})
    return out

def pred_space(atoms,max_lits=2):
    yield Pred(tuple())
    for k in range(1,max_lits+1):
        for names in itertools.combinations(atoms,k):
            for vals in itertools.product((0,1),repeat=k): yield Pred(tuple(zip(names,vals)))

def best(rows,atoms,gvals=None):
    scored=[]
    for p in pred_space(atoms):
        su=un=0; sig=[]
        for i,r in enumerate(rows):
            h=p.holds(r,None if gvals is None else gvals[i]); sig.append(h)
            if h: su+=r['safe']; un+=1-r['safe']
        if su and un==0: scored.append((-su,p.cost,p.encode(),p,tuple(sig)))
    return min(scored,key=lambda z:(z[0],z[1],z[2])) if scored else None

def programs():
    # compositional low-level grammar; no named compound operator menu
    for k in range(16):
        yield (3,f'and(shr(disc_hash,{k}),1)',lambda h,k=k:(h>>k)&1)
        yield (3,f'mod(shr(disc_hash,{k}),2)',lambda h,k=k:(h>>k)%2)
        yield (4,f'neq0(and(shr(disc_hash,{k}),1))',lambda h,k=k:int(((h>>k)&1)!=0))

def main():
    rows=load(sys.argv[1]); safe=sum(r['safe'] for r in rows); unsafe=len(rows)-safe
    print(f'V17_EVENTS total={len(rows)} safe={safe} unsafe={unsafe}')
    if not safe or not unsafe: print('OPERATOR_DEFINITION_GENESIS_V17=UNDERIDENTIFIED'); return 2
    initial=['empty','closed','canonical']+[f'eq{k}' for k in range(16)]+[f'neq{k}' for k in range(16)]
    ib=best(rows,initial); init_cov=-ib[0] if ib else 0
    print(f'V17_INITIAL_FRONTIER safe_coverage={init_cov} rule={ib[2] if ib else "NONE"}')
    if init_cov==safe: print('OPERATOR_DEFINITION_GENESIS_V17=NO_GENESIS_NEEDED'); return 3
    choices=[]
    for pcost,expr,fn in programs():
        gv=[fn(r['hash']) for r in rows]; b=best(rows,['empty','closed','canonical','g'],gv)
        if not b: continue
        cov=-b[0]; total=pcost+b[1]
        print(f'V17_PROGRAM expr={expr} safe_coverage={cov} total_cost={total} rule={b[2]}')
        choices.append((-cov,total,expr,b[2],b[3],tuple(gv)))
    if not choices: print('OPERATOR_DEFINITION_GENESIS_V17=UNDERIDENTIFIED'); return 2
    choices.sort(key=lambda z:(z[0],z[1],z[2],z[3])); best_cov=-choices[0][0]; best_cost=choices[0][1]
    if best_cov<=init_cov: print('OPERATOR_DEFINITION_GENESIS_V17=FALSIFIED'); return 4
    top=[z for z in choices if -z[0]==best_cov and z[1]==best_cost]
    beh={}
    for z in top: beh.setdefault((z[5],tuple(z[4].holds(r,z[5][i]) for i,r in enumerate(rows))),z)
    print(f'V17_BEST_BEHAVIOURAL_CLASSES={len(beh)}')
    if len(beh)!=1: print('OPERATOR_DEFINITION_GENESIS_V17=UNDERIDENTIFIED'); return 2
    z=sorted(beh.values(),key=lambda q:(q[2],q[3]))[0]
    print(f'V17_GENERATED_PROGRAM={z[2]}')
    print(f'V17_GENERATED_PREDICATE={z[3]}')
    print(f'V17_GENERATED_FRONTIER safe_coverage={best_cov}')
    print(f'V17_STRICT_FRONTIER_GAIN={best_cov-init_cov}')
    print('V17_INITIAL_LANGUAGE_INSUFFICIENT=PASS')
    print('V17_UNIQUE_BEST_PROGRAM_BEHAVIOURAL_CLASS=PASS')
    print('V17_EXACT_PROGRAM_ABLATION_FRONTIER=PASS')
    open('/tmp/v17_expr.txt','w').write(z[2]); open('/tmp/v17_predicate.txt','w').write(z[3]); open('/tmp/v17_broad_predicate.txt','w').write('TRUE')

if __name__=='__main__': raise SystemExit(main() or 0)
