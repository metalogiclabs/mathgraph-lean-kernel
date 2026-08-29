#!/usr/bin/env python3
from __future__ import annotations
import csv,itertools,re,sys

BASE=('empty','closed','canonical')
SOURCES=('s0','s1','s2','s3')

def load(p):
    out=[]
    with open(p,newline='') as f:
        for x in csv.DictReader(f):
            out.append({k:(x[k] if k=='corpus' else int(x[k])) for k in x})
    return out

def pred_holds(rule,r,g=None):
    if rule=='TRUE': return True
    for lit in rule.split('&') if rule else ():
        n,v=lit.split('='); v=int(v)
        q=g if n=='g' else r[n]
        if q!=v: return False
    return True

def predicates(atoms,max_lits=2):
    yield 'TRUE'
    for k in range(1,max_lits+1):
        for names in itertools.combinations(atoms,k):
            for vals in itertools.product((0,1),repeat=k):
                yield '&'.join(f'{n}={v}' for n,v in zip(names,vals))

def best_pred(rows,atoms,g=None):
    best=None
    for rule in predicates(atoms):
        su=un=0; sig=[]
        for i,r in enumerate(rows):
            hit=pred_holds(rule,r,None if g is None else g[i]); sig.append(hit)
            if hit:
                if r['safe']: su+=1
                else: un+=1
        if not su or un: continue
        cost=0 if rule=='TRUE' else rule.count('&')+1
        z=(-su,cost,rule,tuple(sig))
        if best is None or z[:3]<best[:3]: best=z
    return best

def programs(src):
    for k in range(16):
        yield (f'and(shr({src},{k}),1)',3)
        yield (f'mod(shr({src},{k}),2)',3)
        yield (f'neq0(and(shr({src},{k}),1))',4)

def eval_prog(expr,r):
    m=re.search(r'shr\((s[0-3]),(\d+)\)',expr)
    if not m: raise ValueError(expr)
    src,k=m.group(1),int(m.group(2)); h=r[src]
    return (h>>k)&1

def score_sources(rows,sources):
    choices=[]
    for src in sources:
        for expr,pcost in programs(src):
            gv=[eval_prog(expr,r) for r in rows]
            b=best_pred(rows,BASE+('g',),gv)
            if not b: continue
            cov=-b[0]; total=1+pcost+b[1]
            choices.append((-cov,total,src,expr,b[2],tuple(gv),b[3],cov))
    choices.sort(key=lambda z:(z[0],z[1],z[2],z[3],z[4]))
    return choices

def main():
    rows=load(sys.argv[1]); safe=sum(r['safe'] for r in rows); unsafe=len(rows)-safe
    print(f'V18_EVENTS total={len(rows)} safe={safe} unsafe={unsafe}')
    if not safe or not unsafe:
        print('SOURCE_OBSERVABLE_GENESIS_V18=UNDERIDENTIFIED'); return 2
    ib=best_pred(rows,BASE)
    init_cov=-ib[0] if ib else 0
    print(f'V18_INITIAL_FRONTIER safe_coverage={init_cov} rule={ib[2] if ib else "NONE"}')
    if init_cov==safe:
        print('SOURCE_OBSERVABLE_GENESIS_V18=NO_GENESIS_NEEDED'); return 3
    ch=score_sources(rows,SOURCES)
    if not ch:
        print('SOURCE_OBSERVABLE_GENESIS_V18=UNDERIDENTIFIED'); return 2
    best_cov=-ch[0][0]; best_cost=ch[0][1]
    if best_cov<=init_cov:
        print('SOURCE_OBSERVABLE_GENESIS_V18=FALSIFIED'); return 4
    top=[z for z in ch if -z[0]==best_cov and z[1]==best_cost]
    classes={}
    for z in top:
        key=(z[5],z[6]); classes.setdefault(key,[]).append(z)
    print(f'V18_BEST_BEHAVIOURAL_CLASSES={len(classes)}')
    if len(classes)!=1:
        print('SOURCE_OBSERVABLE_GENESIS_V18=UNDERIDENTIFIED'); return 2
    eqs=next(iter(classes.values())); eqs.sort(key=lambda z:(z[2],z[3],z[4])); z=eqs[0]
    selected_sources=sorted({q[2] for q in eqs})
    remaining=[s for s in SOURCES if s not in selected_sources]
    ab=score_sources(rows,remaining)
    ab_cov=(-ab[0][0]) if ab else init_cov
    print(f'V18_SELECTED_SOURCE={z[2]}')
    print(f'V18_SELECTED_SOURCE_CLASS={",".join(selected_sources)}')
    print(f'V18_GENERATED_PROGRAM={z[3]}')
    print(f'V18_GENERATED_PREDICATE={z[4]}')
    print(f'V18_GENERATED_FRONTIER safe_coverage={best_cov}')
    print(f'V18_STRICT_FRONTIER_GAIN={best_cov-init_cov}')
    print(f'V18_SOURCE_ABLATION_FRONTIER safe_coverage={ab_cov}')
    if ab_cov>=best_cov:
        print('SOURCE_OBSERVABLE_GENESIS_V18=UNDERIDENTIFIED'); return 2
    print('V18_INITIAL_LANGUAGE_INSUFFICIENT=PASS')
    print('V18_UNIQUE_BEST_SOURCE_PROGRAM_BEHAVIOURAL_CLASS=PASS')
    print('V18_EXACT_SOURCE_ABLATION_FRONTIER=PASS')
    open('/tmp/v18_source.txt','w').write(z[2])
    open('/tmp/v18_expr.txt','w').write(z[3])
    open('/tmp/v18_predicate.txt','w').write(z[4])
    open('/tmp/v18_broad_predicate.txt','w').write('TRUE')

if __name__=='__main__': raise SystemExit(main() or 0)
