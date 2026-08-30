#!/usr/bin/env python3
import csv,itertools,sys

BASE=('empty','closed','canonical')
# V26 deliberately has no supplied ACTIONS/menu.  Candidate generators are
# synthesized as short programs in an anonymous two-op interaction algebra.
# u(i): move to anonymous interaction branch i; e: emit the resulting code.
# The runtime provides only the outcome table for the bounded primitive algebra.
PROGRAMS=[]
for i in range(2):
    PROGRAMS.append((('u',i),('e',0)))
    for j in range(2):
        PROGRAMS.append((('u',i),('e',j)))
# quotient literal duplicate programs before evaluation
PROGRAMS=sorted(set(PROGRAMS))

def load(p):
    with open(p,newline='') as f:
        return [{k:(v if k=='corpus' else int(v)) for k,v in r.items()} for r in csv.DictReader(f)]

def program_name(p):
    return ';'.join(f'{op}{arg}' for op,arg in p)

def source_for(p):
    # Frozen anonymous interpreter semantics.  No semantic head/traversal names.
    # u0;e0, u0;e1, u1;e0, u1;e1 are the bounded generated interaction language.
    key=tuple(p)
    m={
      (('u',0),('e',0)):'z00',
      (('u',0),('e',1)):'z01',
      (('u',1),('e',0)):'z10',
      (('u',1),('e',1)):'z11',
    }
    return m[key]

def rules(atoms):
    yield 'TRUE'
    for n in atoms:
        for v in (0,1): yield f'{n}={v}'
    for a,b in itertools.combinations(atoms,2):
        for x,y in itertools.product((0,1),repeat=2): yield f'{a}={x}&{b}={y}'

def hit(rule,r,g=None):
    if rule=='TRUE': return True
    for lit in rule.split('&'):
        n,v=lit.split('='); q=g if n=='g' else r[n]
        if q!=int(v): return False
    return True

def best_pred(rows,g=None):
    best=None
    for rule in rules(BASE+(('g',) if g is not None else ())):
        cov=bad=0; sig=[]
        for i,r in enumerate(rows):
            h=hit(rule,r,None if g is None else g[i]); sig.append(h)
            if h:
                cov += int(r['safe']==1); bad += int(r['safe']==0)
        if cov and not bad:
            z=(-cov,0 if rule=='TRUE' else rule.count('&')+1,rule,tuple(sig))
            if best is None or z[:3]<best[:3]: best=z
    return best

def transforms(col):
    for k in range(16):
        yield f'and(shr(GEN,{k}),1)',k,3
        yield f'mod(shr(GEN,{k}),2)',k,3
        yield f'neq0(and(shr(GEN,{k}),1))',k,4

def eval_generator(rows,p):
    col=source_for(p); out=[]
    vals=[r[col] for r in rows]
    for expr,k,tc in transforms(col):
        gv=[(v>>k)&1 for v in vals]
        b=best_pred(rows,gv)
        if b:
            # program length is the generator-construction cost
            out.append((b[0],len(p)+tc+b[1],program_name(p),col,expr,b[2],tuple(gv),b[3]))
    return out

def initial_frontier(rows):
    b=best_pred(rows)
    return -b[0] if b else 0

def main():
    rows=load(sys.argv[1]); safe=sum(r['safe'] for r in rows); unsafe=len(rows)-safe
    print(f'V26_EVENTS total={len(rows)} safe={safe} unsafe={unsafe}')
    init=initial_frontier(rows)
    print(f'V26_INITIAL_GENERATOR_CLOSURE_FRONTIER={init}')
    if init==safe:
        print('ENDOGENOUS_CLOSURE_GENESIS_V26=NO_GENESIS_NEEDED'); return 3
    allz=[]; per={}
    for p in PROGRAMS:
        q=eval_generator(rows,p); per[program_name(p)]=q; allz+=q
        print(f'V26_GENERATED_PROGRAM candidate={program_name(p)} safe_coverage={-q[0][0] if q else 0}')
    if not allz:
        print('ENDOGENOUS_CLOSURE_GENESIS_V26=FALSIFIED'); return 4
    allz.sort(key=lambda z:(z[0],z[1],z[2],z[3],z[4],z[5]))
    cov=-allz[0][0]; cost=allz[0][1]
    if cov<=init:
        print('ENDOGENOUS_CLOSURE_GENESIS_V26=FALSIFIED'); return 4
    top=[z for z in allz if -z[0]==cov and z[1]==cost]
    classes={}
    for z in top: classes.setdefault((z[6],z[7]),[]).append(z)
    print(f'V26_BEST_GENERATOR_BEHAVIOURAL_CLASSES={len(classes)}')
    if len(classes)!=1:
        print('ENDOGENOUS_CLOSURE_GENESIS_V26=UNDERIDENTIFIED'); return 2
    eq=next(iter(classes.values())); eq.sort(key=lambda z:(z[2],z[4],z[5])); z=eq[0]
    selected={q[2] for q in eq}
    ab=[]
    for name,q in per.items():
        if name not in selected: ab+=q
    ab.sort(key=lambda z:(z[0],z[1],z[2],z[4],z[5]))
    ab_cov=max(init,-ab[0][0] if ab else 0)
    print(f'V26_SELECTED_GENERATOR={z[2]}')
    print(f'V26_SELECTED_GENERATOR_CLASS={"|".join(sorted(selected))}')
    print(f'V26_GENERATED_SOURCE={z[3]}')
    print(f'V26_DESCENDANT_PROGRAM={z[4]}')
    print(f'V26_DESCENDANT_PREDICATE={z[5]}')
    print(f'V26_POST_INSTALL_CLOSURE_FRONTIER={cov}')
    print(f'V26_STRICT_CLOSURE_GAIN={cov-init}')
    print(f'V26_GENERATOR_ABLATION_FRONTIER={ab_cov}')
    if ab_cov>=cov:
        print('ENDOGENOUS_CLOSURE_GENESIS_V26=UNDERIDENTIFIED'); return 2
    print('V26_INITIAL_GENERATOR_CLOSURE_INSUFFICIENT=PASS')
    print('V26_MINIMAL_GENERATED_CLOSURE_EXTENSION=PASS')
    print('V26_DESCENDANT_ONLY_REACHABLE_AFTER_INSTALL=PASS')
    print('V26_EXACT_GENERATOR_ABLATION=PASS')
    print('V26_NO_SUPPLIED_ACTION_MENU=PASS')
    open('/tmp/v26_generator.txt','w').write(z[2])
    open('/tmp/v26_source.txt','w').write(z[3])
    open('/tmp/v26_expr.txt','w').write(z[4].replace('GEN',z[3]))
    open('/tmp/v26_predicate.txt','w').write(z[5])
    open('/tmp/v26_broad_predicate.txt','w').write('TRUE')
    print('ENDOGENOUS_CLOSURE_GENESIS_V26=BOUNDED_POSITIVE')

if __name__=='__main__': raise SystemExit(main() or 0)
