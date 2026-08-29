#!/usr/bin/env python3
from __future__ import annotations
import csv,itertools,sys

BASE=('empty','closed','canonical')
PATHS=('root.disc','root.rigid.head.disc','root.rigid.spine.disc','context.depth')

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

def path_col(path):
    return {'root.disc':'p0','root.rigid.head.disc':'p1','root.rigid.spine.disc':'p2','context.depth':'p3'}[path]

def path_cost(path): return path.count('.')+1

def programs(path):
    for k in range(16):
        yield (f'and(shr({path},{k}),1)',3)
        yield (f'mod(shr({path},{k}),2)',3)
        yield (f'neq0(and(shr({path},{k}),1))',4)

def eval_prog(expr,path,r):
    h=r[path_col(path)]
    k=int(expr.rsplit(',',1)[1].split(')',1)[0])
    return (h>>k)&1

def score(rows,paths):
    out=[]
    for path in paths:
        for expr,pc in programs(path):
            gv=[eval_prog(expr,path,r) for r in rows]
            b=best_pred(rows,BASE+('g',),gv)
            if not b: continue
            cov=-b[0]; total=path_cost(path)+pc+b[1]
            out.append((-cov,total,path,expr,b[2],tuple(gv),b[3],cov))
    out.sort(key=lambda z:(z[0],z[1],z[2],z[3],z[4]))
    return out

def main():
    rows=load(sys.argv[1]); safe=sum(r['safe'] for r in rows); unsafe=len(rows)-safe
    print(f'V19_EVENTS total={len(rows)} safe={safe} unsafe={unsafe}')
    if not safe or not unsafe:
        print('ACCESS_PATH_GENESIS_V19=UNDERIDENTIFIED'); return 2
    ib=best_pred(rows,BASE); init_cov=-ib[0] if ib else 0
    print(f'V19_INITIAL_FRONTIER safe_coverage={init_cov} rule={ib[2] if ib else "NONE"}')
    if init_cov==safe:
        print('ACCESS_PATH_GENESIS_V19=NO_GENESIS_NEEDED'); return 3
    ch=score(rows,PATHS)
    if not ch:
        print('ACCESS_PATH_GENESIS_V19=UNDERIDENTIFIED'); return 2
    best_cov=-ch[0][0]; best_cost=ch[0][1]
    if best_cov<=init_cov:
        print('ACCESS_PATH_GENESIS_V19=FALSIFIED'); return 4
    top=[z for z in ch if -z[0]==best_cov and z[1]==best_cost]
    classes={}
    for z in top: classes.setdefault((z[5],z[6]),[]).append(z)
    print(f'V19_BEST_BEHAVIOURAL_CLASSES={len(classes)}')
    if len(classes)!=1:
        print('ACCESS_PATH_GENESIS_V19=UNDERIDENTIFIED'); return 2
    eqs=next(iter(classes.values())); eqs.sort(key=lambda z:(z[2],z[3],z[4])); z=eqs[0]
    selected_paths=sorted({q[2] for q in eqs})
    remain=[p for p in PATHS if p not in selected_paths]
    ab=score(rows,remain); ab_cov=(-ab[0][0]) if ab else init_cov
    print(f'V19_SELECTED_PATH={z[2]}')
    print(f'V19_SELECTED_PATH_CLASS={"|".join(selected_paths)}')
    print(f'V19_GENERATED_PROGRAM={z[3]}')
    print(f'V19_GENERATED_PREDICATE={z[4]}')
    print(f'V19_GENERATED_FRONTIER safe_coverage={best_cov}')
    print(f'V19_STRICT_FRONTIER_GAIN={best_cov-init_cov}')
    print(f'V19_PATH_ABLATION_FRONTIER safe_coverage={ab_cov}')
    if ab_cov>=best_cov:
        print('ACCESS_PATH_GENESIS_V19=UNDERIDENTIFIED'); return 2
    print('V19_INITIAL_LANGUAGE_INSUFFICIENT=PASS')
    print('V19_UNIQUE_BEST_PATH_PROGRAM_BEHAVIOURAL_CLASS=PASS')
    print('V19_EXACT_PATH_ABLATION_FRONTIER=PASS')
    open('/tmp/v19_path.txt','w').write(z[2])
    open('/tmp/v19_expr.txt','w').write(z[3])
    open('/tmp/v19_predicate.txt','w').write(z[4])
    open('/tmp/v19_broad_predicate.txt','w').write('TRUE')

if __name__=='__main__': raise SystemExit(main() or 0)
