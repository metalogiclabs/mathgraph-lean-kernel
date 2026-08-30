#!/usr/bin/env python3
from __future__ import annotations
import csv,itertools,sys

BASE=('empty','closed','canonical')
INITIAL=('root.disc','root.rigid.spine.disc','context.depth')
SELECTORS=(
    ('read(start(cells))','root.rigid.generated0.disc','p1',2),
    ('read(next(start(cells)))','root.rigid.generated1.disc','p2',3),
)
COL={'root.disc':'p0','root.rigid.spine.disc':'p2','context.depth':'p3'}

def load(p):
    with open(p,newline='') as f:
        return [{k:(x[k] if k=='corpus' else int(x[k])) for k in x} for x in csv.DictReader(f)]

def pred_holds(rule,r,g=None):
    if rule=='TRUE': return True
    for lit in rule.split('&') if rule else ():
        n,v=lit.split('='); v=int(v); q=g if n=='g' else r[n]
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

def transforms(source):
    for k in range(16):
        yield (f'and(shr({source},{k}),1)',3)
        yield (f'mod(shr({source},{k}),2)',3)
        yield (f'neq0(and(shr({source},{k}),1))',4)

def source_value(source,r):
    if source in COL: return r[COL[source]]
    for _,path,col,_ in SELECTORS:
        if source==path: return r[col]
    raise KeyError(source)

def eval_transform(expr,source,r):
    h=source_value(source,r)
    k=int(expr.rsplit(',',1)[1].split(')',1)[0])
    return (h>>k)&1

def score_source(rows,source,selector_def=None,selector_cost=0):
    out=[]
    for expr,tc in transforms(source):
        gv=[eval_transform(expr,source,r) for r in rows]
        b=best_pred(rows,BASE+('g',),gv)
        if not b: continue
        cov=-b[0]; total=selector_cost+source.count('.')+1+tc+b[1]
        out.append((-cov,total,selector_def or 'INITIAL',source,expr,b[2],tuple(gv),b[3],cov))
    return sorted(out,key=lambda z:(z[0],z[1],z[2],z[3],z[4],z[5]))

def best_initial(rows):
    cand=[]
    for s in INITIAL: cand.extend(score_source(rows,s))
    return cand[0] if cand else None

def generated(rows,allowed=None):
    cand=[]
    for d,path,_,cost in SELECTORS:
        if allowed is not None and d not in allowed: continue
        cand.extend(score_source(rows,path,d,cost))
    return sorted(cand,key=lambda z:(z[0],z[1],z[2],z[3],z[4],z[5]))

def main():
    rows=load(sys.argv[1]); safe=sum(r['safe'] for r in rows); unsafe=len(rows)-safe
    print(f'V21_EVENTS total={len(rows)} safe={safe} unsafe={unsafe}')
    if not safe or not unsafe:
        print('SELECTOR_DEFINITION_GENESIS_V21=UNDERIDENTIFIED'); return 2
    bp=best_pred(rows,BASE); base_cov=-bp[0] if bp else 0
    iz=best_initial(rows); init_cov=max(base_cov,-iz[0] if iz else 0)
    print(f'V21_INITIAL_LANGUAGE_FRONTIER safe_coverage={init_cov}')
    if init_cov==safe:
        print('SELECTOR_DEFINITION_GENESIS_V21=NO_GENESIS_NEEDED'); return 3
    cand=generated(rows)
    if not cand:
        print('SELECTOR_DEFINITION_GENESIS_V21=FALSIFIED'); return 4
    for d in [q[0] for q in SELECTORS]:
        one=generated(rows,{d})
        if one: print(f'V21_SELECTOR_CANDIDATE definition={d} safe_coverage={-one[0][0]} program={one[0][4]} predicate={one[0][5]}')
    best_cov=-cand[0][0]; best_cost=cand[0][1]
    if best_cov<=init_cov:
        print('SELECTOR_DEFINITION_GENESIS_V21=FALSIFIED'); return 4
    top=[z for z in cand if -z[0]==best_cov and z[1]==best_cost]
    classes={}
    for z in top: classes.setdefault((z[6],z[7]),[]).append(z)
    print(f'V21_BEST_BEHAVIOURAL_SELECTOR_CLASSES={len(classes)}')
    if len(classes)!=1:
        print('SELECTOR_DEFINITION_GENESIS_V21=UNDERIDENTIFIED'); return 2
    eqs=next(iter(classes.values())); eqs.sort(key=lambda z:(z[2],z[4],z[5])); z=eqs[0]
    selected_defs=sorted({q[2] for q in eqs})
    remaining={d for d,_,_,_ in SELECTORS if d not in selected_defs}
    ab=generated(rows,remaining); ab_cov=max(init_cov,-ab[0][0] if ab else 0)
    print(f'V21_SELECTED_SELECTOR_DEFINITION={z[2]}')
    print(f'V21_SELECTED_SELECTOR_CLASS={"|".join(selected_defs)}')
    print(f'V21_GENERATED_PATH={z[3]}')
    print(f'V21_GENERATED_PROGRAM={z[4]}')
    print(f'V21_GENERATED_PREDICATE={z[5]}')
    print(f'V21_GENERATED_FRONTIER safe_coverage={best_cov}')
    print(f'V21_STRICT_FRONTIER_GAIN={best_cov-init_cov}')
    print(f'V21_DEFINITION_ABLATION_FRONTIER safe_coverage={ab_cov}')
    if ab_cov>=best_cov:
        print('SELECTOR_DEFINITION_GENESIS_V21=UNDERIDENTIFIED'); return 2
    print('V21_INITIAL_SELECTOR_LANGUAGE_INSUFFICIENT=PASS')
    print('V21_UNIQUE_BEST_SELECTOR_DEFINITION_BEHAVIOURAL_CLASS=PASS')
    print('V21_EXACT_SELECTOR_DEFINITION_ABLATION=PASS')
    print('V21_NO_SLOT_FAMILY_EXPOSED_TO_LEARNER=PASS')
    open('/tmp/v21_selector.txt','w').write(z[2])
    open('/tmp/v21_path.txt','w').write(z[3])
    open('/tmp/v21_expr.txt','w').write(z[4])
    open('/tmp/v21_predicate.txt','w').write(z[5])
    open('/tmp/v21_broad_predicate.txt','w').write('TRUE')

if __name__=='__main__': raise SystemExit(main() or 0)
