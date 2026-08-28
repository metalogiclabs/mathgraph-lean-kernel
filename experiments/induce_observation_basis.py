#!/usr/bin/env python3
from __future__ import annotations

import argparse
import itertools
from collections import defaultdict


def parse(path):
    prod = {}
    residuals = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if line.startswith('MSI_PROD|'):
                _, sid, *atoms = line.split('|')
                prod[sid]=tuple(atoms)
            elif line.startswith('MSI_RES|'):
                _, sid, ctx, outcome = line.split('|')
                residuals.append((sid,ctx,outcome))
    return prod,residuals


def exact_basis(prod,residuals):
    # Search subsets of anonymous producer coordinates. A subset is admissible
    # iff no two observations with the same context and selected signature
    # require different protected outcomes. First cardinality is therefore
    # minimal in the frozen coordinate grammar.
    n = len(next(iter(prod.values())))
    for k in range(n+1):
        good=[]
        for idxs in itertools.combinations(range(n),k):
            table={}
            ok=True
            for sid,ctx,out in residuals:
                if sid not in prod: continue
                sig=(ctx,)+tuple(prod[sid][i] for i in idxs)
                old=table.get(sig)
                if old is not None and old != out:
                    ok=False; break
                table[sig]=out
            if ok:
                good.append(idxs)
        if good:
            return good
    return []


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('trace')
    ap.add_argument('label')
    args=ap.parse_args()
    prod,residuals=parse(args.trace)
    if not prod or not residuals:
        raise SystemExit('missing producer or residual rows')
    usable=[r for r in residuals if r[0] in prod]
    bases=exact_basis(prod,usable)
    if not bases:
        raise SystemExit('no exact basis in frozen grammar')
    width=len(bases[0])
    print(f'{args.label}_PRODUCERS={len(prod)}')
    print(f'{args.label}_RESIDUALS={len(usable)}')
    print(f'{args.label}_MIN_BASIS_WIDTH={width}')
    print(f'{args.label}_MIN_BASIS_COUNT={len(bases)}')
    print(f'{args.label}_MIN_BASES={";".join(",".join(map(str,b)) or "EMPTY" for b in bases)}')
    print(f'{args.label}_UNIQUE_MINIMAL={"PASS" if len(bases)==1 else "NO"}')
    print(f'{args.label}_RESIDUAL_TO_OBSERVATION_BASIS=PASS')

if __name__=='__main__':
    main()
