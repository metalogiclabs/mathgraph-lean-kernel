#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import itertools, json, re, sys

trace=Path(sys.argv[1])
root=Path(sys.argv[2])
stage=int(sys.argv[3]) if len(sys.argv)>3 else 2
intervention=Path(sys.argv[4]) if len(sys.argv)>4 and sys.argv[4] != '-' else None
promoted_manifest=Path(sys.argv[5]) if len(sys.argv)>5 and sys.argv[5] != '-' else None


def read_trace(path):
    prod={}; residuals=[]
    for line in path.read_text().splitlines():
        if line.startswith('MSI_PROD|'):
            _,sid,*atoms=line.split('|'); prod[sid]=tuple(map(int,atoms))
        elif line.startswith('MSI_RES|'):
            _,sid,ctx,out=line.split('|'); residuals.append((sid,ctx,int(out)))
    return prod,residuals

prod,residuals=read_trace(trace)
if not prod or not residuals: raise SystemExit('missing trace rows')
iproduct, iresiduals = read_trace(intervention) if intervention else ({},[])

# Minimum anonymous coordinate bases within one protected future context.
def bases_for(ctx, p=prod, rs=residuals):
    rows=[r for r in rs if r[0] in p and r[1]==ctx]
    n=len(next(iter(p.values())))
    for k in range(n+1):
        good=[]
        for idxs in itertools.combinations(range(n),k):
            tab={}; ok=True
            for sid,_,out in rows:
                sig=tuple(p[sid][i] for i in idxs)
                if sig in tab and tab[sig]!=out: ok=False; break
                tab[sig]=out
            if ok: good.append(idxs)
        if good: return rows,good
    return rows,[]


def sufficient_on_union(ctx,basis):
    tab={}
    for p,rs in ((prod,residuals),(iproduct,iresiduals)):
        for sid,c,out in rs:
            if c!=ctx or sid not in p: continue
            sig=tuple(p[sid][i] for i in basis)
            if sig in tab and tab[sig]!=out:
                return False
            tab[sig]=out
    return True


def choose_unique(ctx):
    rows,bs=bases_for(ctx)
    if not rows: raise SystemExit(f'{ctx}: no rows')
    if len(bs)>1 and intervention:
        survivors=[b for b in bs if sufficient_on_union(ctx,b)]
        print(f'{ctx.upper()}_TRAIN_AMBIGUOUS_BASES={bs}')
        print(f'{ctx.upper()}_INTERVENTION_SURVIVORS={survivors}')
        if len(survivors)==1:
            bs=survivors
            print(f'{ctx.upper()}_NEW_CONSEQUENCE_SEPARATOR=PASS')
    if len(bs)!=1:
        raise SystemExit(f'{ctx}: minimum basis not unique after available consequences: {bs}')
    print(f'{ctx.upper()}_UNIQUE_MIN_BASIS={",".join(map(str,bs[0])) or "EMPTY"}')
    return bs[0]

# Development is stage-local: generation 1 may only use q0. Generation 2 may
# use q1 only after consuming the constructor promoted by generation 1. q2 is
# a diagnostic future residual and is never allowed to retroactively kill an
# earlier generation.
chosen={'q0': choose_unique('q0')}
if stage>=2:
    if promoted_manifest is None or not promoted_manifest.exists():
        raise SystemExit('STAGE2_PROMOTION_REQUIRED: generated guard constructor absent')
    manifest=json.loads(promoted_manifest.read_text())
    if manifest.get('constructor')!='anonymous_guard_before_force':
        raise SystemExit('STAGE2_PROMOTION_REQUIRED: wrong promoted constructor')
    print('STAGE2_PROMOTED_CONSTRUCTOR_CONSUMED=PASS')
    chosen['q1']=choose_unique('q1')

# Recover the representation vocabulary from checker source rather than a
# hand-maintained semantic lowering table.
value_src=(root/'src/value.rs').read_text()
def enum_variants(name):
    m=re.search(rf'pub enum {name}<[^>]+>\s*\{{(.*?)\n\}}',value_src,re.S)
    if not m: raise SystemExit(f'cannot parse enum {name}')
    body=m.group(1)
    out=[]; depth=0; token=''
    for ch in body:
        token+=ch
        if ch=='{': depth+=1
        elif ch=='}': depth-=1
        elif ch==',' and depth==0:
            x=token[:-1].strip(); token=''
            if x:
                nm=re.match(r'([A-Za-z_][A-Za-z0-9_]*)',x)
                if nm: out.append(nm.group(1))
    return out
value_variants=enum_variants('Value')
print('SOURCE_DERIVED_VALUE_VARIANTS='+','.join(value_variants))

# Positive signatures are learned from verified consequences, not labels.
def positive_sig(ctx,basis):
    pos=set(); neg=set()
    for p,rs in ((prod,residuals),(iproduct,iresiduals)):
        for sid,c,out in rs:
            if c!=ctx or sid not in p: continue
            ss=tuple(p[sid][i] for i in basis)
            (pos if out==1 else neg).add(ss)
    if len(pos)!=1 or pos & neg: raise SystemExit(f'{ctx}: no unique positive signature: pos={pos} overlap={pos&neg}')
    return next(iter(pos))

sig={ctx:positive_sig(ctx,b) for ctx,b in chosen.items()}
print('ANONYMOUS_POSITIVE_SIGNATURES='+';'.join(f'{k}:{sig[k]}' for k in chosen))

if chosen['q0']!=(0,): raise SystemExit(f'q0 expected one-coordinate generated guard, got {chosen["q0"]}')
q0v=value_variants[sig['q0'][0]]
print(f'STAGE1_GENERATED_VARIANT={q0v}')

infer=root/'src/infer.rs'; s=infer.read_text()
old='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
if q0v!='Sort': raise SystemExit(f'stage1 source-derived shape is {q0v}; template contract requires level-bearing variant')
new='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        if let Value::Sort { level, .. } = v { return *level; }\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
if old not in s: raise SystemExit('stage1 consumer template not found')
s=s.replace(old,new,1)

if stage==1:
    # The learned representation is promoted as a generic constructor, not as
    # the literal semantic name Sort. Stage 2 must possess this artifact.
    m={
        'constructor':'anonymous_guard_before_force',
        'source_context':'q0',
        'basis':list(chosen['q0']),
        'positive_signature':list(sig['q0'])
    }
    (root/'.msi-stage1-promotion.json').write_text(json.dumps(m,sort_keys=True)+'\n')
    print('STAGE1_CONSTRUCTOR_PROMOTION=PASS')
else:
    if chosen['q1']!=(0,): raise SystemExit(f'q1 must be expressible by promoted top-level guard, got {chosen["q1"]}')
    q1v=value_variants[sig['q1'][0]]
    if q0v==q1v: raise SystemExit('second generated interface did not change runtime distinction')
    print(f'STAGE2_GENERATED_VARIANT={q1v}')
    old='''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };'''
    if q1v!='Pi': raise SystemExit(f'stage2 source-derived shape is {q1v}; template contract requires domain/body variant')
    new='''        while let Some(arg) = args.pop() {\n            let (domain, body) = match fty {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => {\n                    let fty_f = self.force_all(depth, fty);\n                    match fty_f {\n                        Value::Pi { domain, body, .. } => (*domain, body),\n                        _ => panic!("expected a pi type"),\n                    }\n                }\n            };'''
    if old not in s: raise SystemExit('stage2 consumer template not found')
    s=s.replace(old,new,1)
    print('STAGE2_DEPENDS_ON_PROMOTED_GUARD=PASS')
    print('SECOND_STRUCTURALLY_DISTINCT_INTERFACE=PASS')

    # Prospective q2 residual: test whether new verified experience actually
    # warrants another distinction. If two bases remain sufficient after the
    # intervention, the correct MSI action is to refuse an unjustified split.
    rows2,bs2=bases_for('q2')
    if rows2:
        surv=[b for b in bs2 if sufficient_on_union('q2',b)] if intervention else bs2
        print(f'Q2_PROSPECTIVE_BASES={bs2}')
        print(f'Q2_POST_INTERVENTION_SURVIVORS={surv}')
        if len(surv)>1:
            print('Q2_NO_JUSTIFIED_REFINEMENT=PASS')
            print('MINIMALITY_STOP_RULE=PASS')
        elif len(surv)==1:
            print('Q2_NEW_SEPARATOR_AVAILABLE=PASS')

infer.write_text(s)
print(f'BLIND_RECURSIVE_LOWERING_STAGE={stage}:PASS')
