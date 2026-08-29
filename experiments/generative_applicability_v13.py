#!/usr/bin/env python3
"""V13 anonymous applicability predicate synthesis.

This experiment intentionally treats runtime observations as anonymous feature vectors.
It never exposes semantic RigidHead names to the learner.  The workflow supplies a CSV
of rows: corpus,event_id,safe,f0,f1,... where safe is verifier-derived and feature names
are opaque indices.  We enumerate conjunctions in increasing description length and
return the unique minimum predicate with positive safe coverage and zero unsafe coverage.
"""
from __future__ import annotations
import csv
import itertools
import json
import sys
from dataclasses import dataclass

@dataclass(frozen=True)
class Lit:
    idx: int
    val: int

@dataclass(frozen=True)
class Pred:
    lits: tuple[Lit, ...]

    def holds(self, xs: tuple[int, ...]) -> bool:
        return all(xs[l.idx] == l.val for l in self.lits)

    @property
    def cost(self) -> int:
        return len(self.lits)

    def encode(self) -> str:
        return '&'.join(f'f{x.idx}={x.val}' for x in self.lits) or 'TRUE'


def load(path: str):
    rows=[]
    with open(path, newline='') as f:
        r=csv.reader(f)
        hdr=next(r)
        assert hdr[:3]==['corpus','event_id','safe'], hdr
        for row in r:
            rows.append((row[0], row[1], int(row[2]), tuple(map(int,row[3:]))))
    return rows, len(hdr)-3


def candidates(nfeat: int, max_lits: int):
    atoms=[Lit(i,v) for i in range(nfeat) for v in (0,1)]
    for k in range(1,max_lits+1):
        for combo in itertools.combinations(atoms,k):
            idxs=[x.idx for x in combo]
            if len(set(idxs)) != len(idxs):
                continue
            yield Pred(tuple(combo))


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: generative_applicability_v13.py observations.csv max_literals')
    rows,nfeat=load(sys.argv[1]); max_lits=int(sys.argv[2])
    safe=sum(y for _,_,y,_ in rows); unsafe=len(rows)-safe
    print(f'V13_EVENTS total={len(rows)} safe={safe} unsafe={unsafe} features={nfeat}')
    if safe==0 or unsafe==0:
        print('GENERATIVE_APPLICABILITY_V13=UNDERIDENTIFIED')
        return 2

    licensed=[]
    for p in candidates(nfeat,max_lits):
        covered_safe=sum(1 for _,_,y,x in rows if y and p.holds(x))
        covered_unsafe=sum(1 for _,_,y,x in rows if not y and p.holds(x))
        if covered_safe>0 and covered_unsafe==0:
            licensed.append((p.cost,-covered_safe,p,covered_safe))
    if not licensed:
        print('V13_NO_LICENSED_PREDICATE=1')
        print('GENERATIVE_APPLICABILITY_V13=UNDERIDENTIFIED')
        return 2
    licensed.sort(key=lambda z:(z[0],z[1],z[2].encode()))
    best_cost=licensed[0][0]
    best_cov=-licensed[0][1]
    minima=[z for z in licensed if z[0]==best_cost and -z[1]==best_cov]
    behavioural=[]
    for z in minima:
        sig=tuple(z[2].holds(x) for *_,x in rows)
        if not any(sig==s for s,_ in behavioural):
            behavioural.append((sig,z))
    if len(behavioural)!=1:
        print(f'V13_MINIMUM_BEHAVIOURAL_CLASSES={len(behavioural)}')
        for _,z in behavioural[:20]: print('V13_AMBIGUOUS='+z[2].encode())
        print('GENERATIVE_APPLICABILITY_V13=UNDERIDENTIFIED')
        return 2
    z=behavioural[0][1]; p=z[2]
    print('V13_PREDICATE='+p.encode())
    print(f'V13_PREDICATE_COST={p.cost}')
    print(f'V13_SAFE_COVERAGE={z[3]}')
    # nearest generated broadening: remove one literal, prefer greatest event coverage
    broad=[]
    if p.cost>1:
        for i in range(p.cost):
            q=Pred(p.lits[:i]+p.lits[i+1:])
            cov=sum(q.holds(x) for *_,x in rows)
            broad.append((-cov,q))
    else:
        broad.append((-len(rows),Pred(tuple())))
    broad.sort(key=lambda z:(z[0],z[1].encode()))
    print('V13_BROAD_PREDICATE='+broad[0][1].encode())
    with open('/tmp/v13_predicate.json','w') as f:
        json.dump({'predicate':[[l.idx,l.val] for l in p.lits],
                   'broad':[[l.idx,l.val] for l in broad[0][1].lits]},f)
    print('V13_UNIQUE_MINIMUM_GENERATED_PREDICATE=PASS')

if __name__=='__main__':
    main()
