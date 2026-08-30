#!/usr/bin/env python3
from __future__ import annotations
import csv, sys
from collections import defaultdict

VISIBLE = ('p0','p3','empty','closed','canonical')

def load(path):
    rows=[]
    with open(path,newline='') as f:
        for r in csv.DictReader(f):
            rows.append({k:(r[k] if k=='corpus' else int(r[k])) for k in r})
    return rows

def sig(r, cols=VISIBLE):
    return tuple(r[c] for c in cols)

def main():
    rows=load(sys.argv[1])
    safe=sum(r['safe'] for r in rows); unsafe=len(rows)-safe
    print(f'V23_EVENTS total={len(rows)} safe={safe} unsafe={unsafe}')
    if not safe or not unsafe:
        print('OBSERVATION_CLOSURE_BOUNDARY_V23=UNDERIDENTIFIED'); return 2

    classes=defaultdict(lambda:[0,0,[]])
    for r in rows:
        z=classes[sig(r)]
        z[r['safe']]+=1
        if len(z[2])<4: z[2].append((r['corpus'],r['event_id'],r['safe']))
    mixed=[(s,v) for s,v in classes.items() if v[0] and v[1]]
    pure_safe=sum(v[1] for v in classes.values() if v[1] and not v[0])
    mixed_safe=sum(v[1] for _,v in mixed)
    mixed_unsafe=sum(v[0] for _,v in mixed)
    print(f'V23_VISIBLE_SIGNATURE_CLASSES={len(classes)}')
    print(f'V23_MIXED_LABEL_CLASSES={len(mixed)} mixed_safe={mixed_safe} mixed_unsafe={mixed_unsafe}')
    print(f'V23_UNIVERSAL_ZERO_UNSAFE_SAFE_BOUND={pure_safe}')
    if mixed:
        s,v=mixed[0]
        print('V23_COLLISION_WITNESS_SIGNATURE=' + ','.join(map(str,s)))
        print('V23_COLLISION_WITNESS_EVENTS=' + '|'.join(f'{c}:{e}:{y}' for c,e,y in v[2]))
    if not mixed or pure_safe>=safe:
        print('OBSERVATION_CLOSURE_BOUNDARY_V23=NO_INFORMATION_BOUNDARY'); return 3

    # Previously validated V22 substrate source sigma0 is p1.  Freeze the exact
    # V22 generated observation and predicate; this is not searched in V23.
    def g(r): return (r['p1'] >> 13) & 1
    selected=[r for r in rows if g(r)==1]
    s2=sum(r['safe'] for r in selected); u2=sum(1-r['safe'] for r in selected)
    print(f'V23_V22_SIGMA0_WITNESS safe_coverage={s2} unsafe_coverage={u2}')
    if s2!=safe or u2!=0:
        print('OBSERVATION_CLOSURE_BOUNDARY_V23=V22_WITNESS_INCONSISTENT'); return 4

    # Show the added source strictly refines at least one mixed old class.
    broken=0
    for oldsig,v in mixed:
        rs=[r for r in rows if sig(r)==oldsig]
        sub=defaultdict(set)
        for r in rs: sub[g(r)].add(r['safe'])
        if len(sub)>1 and any(len(labels)==1 for labels in sub.values()): broken+=1
    print(f'V23_MIXED_CLASSES_REFINED_BY_SIGMA0={broken}')
    if not broken:
        print('OBSERVATION_CLOSURE_BOUNDARY_V23=V22_WITNESS_INCONSISTENT'); return 4

    print('V23_REAL_SAFE_UNSAFE_COLLISION=PASS')
    print('V23_UNIVERSAL_FACTOR_THROUGH_SIGNATURE_BOUND=PASS')
    print('V23_BOUND_STRICTLY_BELOW_FULL_SAFE_FRONTIER=PASS')
    print('V23_NEW_PRIMITIVE_SOURCE_BREAKS_OBSTRUCTION=PASS')
    open('/tmp/v23_analysis.txt','w').write(
        f'events={len(rows)} safe={safe} unsafe={unsafe}\n'
        f'visible_classes={len(classes)} mixed={len(mixed)}\n'
        f'universal_zero_unsafe_safe_bound={pure_safe}\n'
        f'sigma0_safe={s2} sigma0_unsafe={u2}\n'
        f'mixed_classes_refined={broken}\n')
    return 0

if __name__=='__main__': raise SystemExit(main())
