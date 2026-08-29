#!/usr/bin/env python3
from __future__ import annotations
import csv,itertools,sys
from dataclasses import dataclass

BASE=(12,13,14)
GENERATED=tuple(range(12))

@dataclass(frozen=True)
class Lit:
    idx:int
    val:int

@dataclass(frozen=True)
class Pred:
    lits:tuple[Lit,...]
    def holds(self,x): return all(x[z.idx]==z.val for z in self.lits)
    def encode(self): return '&'.join(f'f{z.idx}={z.val}' for z in self.lits) or 'TRUE'
    @property
    def cost(self): return len(self.lits)

def load(path):
    rows=[]
    with open(path,newline='') as f:
        r=csv.reader(f); hdr=next(r)
        assert hdr[:3]==['corpus','event_id','safe']
        for row in r: rows.append((row[0],row[1],int(row[2]),tuple(map(int,row[3:]))))
    return rows

def preds(features,max_lits):
    yield Pred(tuple())
    atoms=[Lit(i,v) for i in features for v in (0,1)]
    for k in range(1,max_lits+1):
        for cs in itertools.combinations(atoms,k):
            if len({z.idx for z in cs})==k: yield Pred(tuple(cs))

def frontier(rows,features,max_lits):
    scored=[]
    for p in preds(features,max_lits):
        su=sum(1 for *_,y,x in rows if y and p.holds(x))
        un=sum(1 for *_,y,x in rows if not y and p.holds(x))
        if su>0 and un==0: scored.append((-su,p.cost,p.encode(),p,su))
    if not scored: return None,[]
    scored.sort(key=lambda z:(z[0],z[1],z[2]))
    cov=-scored[0][0]; cost=scored[0][1]
    tied=[z for z in scored if -z[0]==cov and z[1]==cost]
    classes={}
    for z in tied:
        sig=tuple(z[3].holds(x) for *_,x in rows)
        classes.setdefault(sig,z)
    return (cov,cost),list(classes.values())

def broader(p,rows):
    qs=[]
    if p.cost==0: return p
    for i in range(p.cost):
        q=Pred(p.lits[:i]+p.lits[i+1:])
        qs.append((-sum(q.holds(x) for *_,x in rows),q.encode(),q))
    qs.sort(key=lambda z:(z[0],z[1])); return qs[0][2]

def main():
    if len(sys.argv)!=3: raise SystemExit('usage: feature_language_genesis_v14.py observations.csv max_literals')
    rows=load(sys.argv[1]); max_lits=int(sys.argv[2])
    safe=sum(y for *_,y,_ in rows); unsafe=len(rows)-safe
    print(f'V14_EVENTS total={len(rows)} safe={safe} unsafe={unsafe}')
    if not safe or not unsafe:
        print('FEATURE_LANGUAGE_GENESIS_V14=UNDERIDENTIFIED'); return 2

    base_score,base_classes=frontier(rows,BASE,max_lits)
    base_cov=base_score[0] if base_score else 0
    base_cost=base_score[1] if base_score else -1
    print(f'V14_INITIAL_FRONTIER safe_coverage={base_cov} cost={base_cost} behavioural_classes={len(base_classes)}')
    if base_classes:
        for z in base_classes[:10]: print('V14_INITIAL_PREDICATE='+z[3].encode())

    choices=[]
    for k in GENERATED:
        score,classes=frontier(rows,BASE+(k,),max_lits)
        if not score: continue
        cov,cost=score
        for z in classes:
            p=z[3]
            sig=tuple(p.holds(x) for *_,x in rows)
            choices.append((-cov,cost,k,p.encode(),sig,p,cov))
            print(f'V14_GENERATED_CANDIDATE p{k} safe_coverage={cov} cost={cost} rule={p.encode()}')
    if not choices:
        print('FEATURE_LANGUAGE_GENESIS_V14=UNDERIDENTIFIED'); return 2
    choices.sort(key=lambda z:(z[0],z[1],z[2],z[3]))
    best_cov=-choices[0][0]; best_cost=choices[0][1]
    if best_cov<=base_cov:
        print(f'V14_NO_STRICT_FRONTIER_EXPANSION initial={base_cov} generated={best_cov}')
        print('FEATURE_LANGUAGE_GENESIS_V14=NO_GENESIS_NEEDED'); return 3

    top=[z for z in choices if -z[0]==best_cov and z[1]==best_cost]
    beh={}
    for z in top: beh.setdefault(z[4],z)
    print(f'V14_BEST_BEHAVIOURAL_CLASSES={len(beh)}')
    if len(beh)!=1:
        for z in list(beh.values())[:20]: print(f'V14_AMBIGUOUS_PROBE=p{z[2]} rule={z[5].encode()}')
        print('FEATURE_LANGUAGE_GENESIS_V14=UNDERIDENTIFIED'); return 2

    z=next(iter(beh.values())); bit=z[2]; p=z[5]
    # Pick the smallest concrete probe realizing the unique best behavioural class.
    same=[q for q in top if q[4]==z[4]]; bit=min(q[2] for q in same)
    concrete=[q for q in same if q[2]==bit]; concrete.sort(key=lambda q:q[3]); p=concrete[0][5]
    b=broader(p,rows)
    uses_generated=any(l.idx==bit for l in p.lits)
    assert uses_generated, 'strict frontier expansion without generated probe in rule'
    print(f'V14_GENERATED_PROBE=p{bit}')
    print(f'V14_GENERATED_PREDICATE={p.encode()}')
    print(f'V14_GENERATED_FRONTIER safe_coverage={best_cov} cost={p.cost}')
    print(f'V14_BROAD_PREDICATE={b.encode()}')
    print(f'V14_STRICT_FRONTIER_GAIN={best_cov-base_cov}')
    print('V14_INITIAL_LANGUAGE_INSUFFICIENT=PASS')
    print('V14_UNIQUE_BEST_GENERATED_BEHAVIOURAL_CLASS=PASS')
    print('V14_EXACT_PROBE_ABLATION_FRONTIER=PASS')
    open('/tmp/v14_probe.txt','w').write(str(bit))
    open('/tmp/v14_predicate.txt','w').write(p.encode())
    open('/tmp/v14_broad_predicate.txt','w').write(b.encode())

if __name__=='__main__': main()
