#!/usr/bin/env python3
from __future__ import annotations
import csv,itertools,sys

BASE=('empty','closed','canonical')
INITIAL=('root.disc','root.rigid.spine.disc','context.depth')
EXTENSIONS={
    'slot(0)':'root.rigid.slot0.disc',
    'slot(1)':'root.rigid.slot1.disc',
}
COL={
    'root.disc':'p0',
    'root.rigid.slot0.disc':'p1',
    'root.rigid.slot1.disc':'p2',
    'root.rigid.spine.disc':'p2',
    'context.depth':'p3',
}

def load(p):
    with open(p,newline='') as f:
        return [{k:(x[k] if k=='corpus' else int(x[k])) for k in x} for x in csv.DictReader(f)]

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

def programs(path):
    for k in range(16):
        yield (f'and(shr({path},{k}),1)',3)
        yield (f'mod(shr({path},{k}),2)',3)
        yield (f'neq0(and(shr({path},{k}),1))',4)

def eval_prog(expr,path,r):
    h=r[COL[path]]
    k=int(expr.rsplit(',',1)[1].split(')',1)[0])
    return (h>>k)&1

def path_cost(path): return path.count('.')+1

def score(rows,paths):
    out=[]
    for path in paths:
        for expr,pc in programs(path):
            gv=[eval_prog(expr,path,r) for r in rows]
            b=best_pred(rows,BASE+('g',),gv)
            if not b: continue
            cov=-b[0]; total=path_cost(path)+pc+b[1]
            out.append((-cov,total,path,expr,b[2],tuple(gv),b[3],cov))
    return sorted(out,key=lambda z:(z[0],z[1],z[2],z[3],z[4]))

def best_frontier(rows,paths):
    s=score(rows,paths)
    if not s: return None,0
    return s[0],-s[0][0]

def main():
    rows=load(sys.argv[1]); safe=sum(r['safe'] for r in rows); unsafe=len(rows)-safe
    print(f'V20_EVENTS total={len(rows)} safe={safe} unsafe={unsafe}')
    if not safe or not unsafe:
        print('ACCESS_PATH_GRAMMAR_GENESIS_V20=UNDERIDENTIFIED'); return 2
    ib=best_pred(rows,BASE); base_cov=-ib[0] if ib else 0
    iz,init_cov=best_frontier(rows,INITIAL)
    init_cov=max(init_cov,base_cov)
    print(f'V20_INITIAL_GRAMMAR_FRONTIER safe_coverage={init_cov}')
    if init_cov==safe:
        print('ACCESS_PATH_GRAMMAR_GENESIS_V20=NO_GENESIS_NEEDED'); return 3

    candidates=[]
    for ext,path in EXTENSIONS.items():
        z,cov=best_frontier(rows,INITIAL+(path,))
        if z:
            candidates.append(( -cov,z[1],ext,path,z ))
            print(f'V20_EXTENSION_CANDIDATE extension={ext} safe_coverage={cov} program={z[3]} predicate={z[4]}')
    if not candidates:
        print('ACCESS_PATH_GRAMMAR_GENESIS_V20=FALSIFIED'); return 4
    candidates.sort(key=lambda x:(x[0],x[1],x[2]))
    best_cov=-candidates[0][0]; best_cost=candidates[0][1]
    if best_cov<=init_cov:
        print('ACCESS_PATH_GRAMMAR_GENESIS_V20=FALSIFIED'); return 4
    top=[x for x in candidates if -x[0]==best_cov and x[1]==best_cost]
    classes={}
    for x in top:
        z=x[4]
        classes.setdefault((z[5],z[6]),[]).append(x)
    print(f'V20_BEST_BEHAVIOURAL_EXTENSION_CLASSES={len(classes)}')
    if len(classes)!=1:
        print('ACCESS_PATH_GRAMMAR_GENESIS_V20=UNDERIDENTIFIED'); return 2
    eqs=next(iter(classes.values())); eqs.sort(key=lambda x:x[2]); x=eqs[0]; z=x[4]
    selected_exts=sorted({q[2] for q in eqs})
    # Exact grammar ablation: remove selected extension productions and rerun from initial grammar plus remaining generated productions.
    remain=INITIAL+tuple(path for ext,path in EXTENSIONS.items() if ext not in selected_exts)
    _,ab_cov=best_frontier(rows,remain); ab_cov=max(ab_cov,base_cov)
    print(f'V20_SELECTED_EXTENSION={x[2]}')
    print(f'V20_SELECTED_EXTENSION_CLASS={"|".join(selected_exts)}')
    print(f'V20_GENERATED_PATH={x[3]}')
    print(f'V20_GENERATED_PROGRAM={z[3]}')
    print(f'V20_GENERATED_PREDICATE={z[4]}')
    print(f'V20_GENERATED_FRONTIER safe_coverage={best_cov}')
    print(f'V20_STRICT_FRONTIER_GAIN={best_cov-init_cov}')
    print(f'V20_SELECTOR_ABLATION_FRONTIER safe_coverage={ab_cov}')
    if ab_cov>=best_cov:
        print('ACCESS_PATH_GRAMMAR_GENESIS_V20=UNDERIDENTIFIED'); return 2
    print('V20_INITIAL_PATH_GRAMMAR_INSUFFICIENT=PASS')
    print('V20_UNIQUE_BEST_SELECTOR_EXTENSION_BEHAVIOURAL_CLASS=PASS')
    print('V20_EXACT_SELECTOR_PRODUCTION_ABLATION=PASS')
    open('/tmp/v20_extension.txt','w').write(x[2])
    open('/tmp/v20_path.txt','w').write(x[3])
    open('/tmp/v20_expr.txt','w').write(z[3])
    open('/tmp/v20_predicate.txt','w').write(z[4])
    open('/tmp/v20_broad_predicate.txt','w').write('TRUE')

if __name__=='__main__': raise SystemExit(main() or 0)
