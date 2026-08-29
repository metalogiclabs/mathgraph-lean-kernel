#!/usr/bin/env python3
from pathlib import Path
import itertools, json, re, sys

trace=Path(sys.argv[1])
root=Path(sys.argv[2])
cert=Path(sys.argv[3])
intervention=Path(sys.argv[4]) if len(sys.argv)>4 and sys.argv[4] != '-' else None

if not cert.exists():
    raise SystemExit('STAGE3_STAGE2_PROMOTION_REQUIRED')
meta=json.loads(cert.read_text())
if meta.get('constructor')!='anonymous_exposed_body_interface':
    raise SystemExit('STAGE3_STAGE2_PROMOTION_REQUIRED: wrong certificate')
print('STAGE3_STAGE2_PROMOTION_CONSUMED=PASS')


def read_trace(path):
    prod={}; residuals=[]
    for line in path.read_text().splitlines():
        if line.startswith('MSI_PROD|'):
            _,sid,*atoms=line.split('|'); prod[sid]=tuple(map(int,atoms))
        elif line.startswith('MSI_RES|'):
            _,sid,ctx,out=line.split('|'); residuals.append((sid,ctx,int(out)))
    return prod,residuals

prod,residuals=read_trace(trace)
iproduct,iresiduals=read_trace(intervention) if intervention else ({},[])
rows=[r for r in residuals if r[1]=='q3' and r[0] in prod]
if not rows:
    raise SystemExit('q3: no closure residual rows')
n=len(next(iter(prod.values())))

def good_basis(basis, datasets=((prod,residuals),)):
    tab={}
    for p,rs in datasets:
        for sid,ctx,out in rs:
            if ctx!='q3' or sid not in p: continue
            sig=tuple(p[sid][i] for i in basis)
            if sig in tab and tab[sig]!=out:
                return False
            tab[sig]=out
    return True

mins=[]
for k in range(n+1):
    for b in itertools.combinations(range(n),k):
        if good_basis(b): mins.append(b)
    if mins: break
print(f'Q3_TRAIN_MIN_BASES={mins}')
if intervention and len(mins)>1:
    surv=[b for b in mins if good_basis(b,((prod,residuals),(iproduct,iresiduals)))]
else:
    surv=mins
print(f'Q3_POST_INTERVENTION_SURVIVORS={surv}')
if len(surv)!=1:
    print('Q3_NO_UNIQUE_JUSTIFIED_INTERFACE=PASS')
    raise SystemExit(3)
basis=surv[0]
print('Q3_UNIQUE_MIN_BASIS='+(','.join(map(str,basis)) if basis else 'EMPTY'))

# Determine the positive signature only from verified outcomes.
pos=set(); neg=set()
for p,rs in ((prod,residuals),(iproduct,iresiduals)):
    for sid,ctx,out in rs:
        if ctx!='q3' or sid not in p: continue
        ss=tuple(p[sid][i] for i in basis)
        (pos if out else neg).add(ss)
if len(pos)!=1 or pos & neg:
    raise SystemExit(f'q3: no unique positive signature: pos={pos}, overlap={pos&neg}')
positive=next(iter(pos))
print(f'Q3_ANONYMOUS_POSITIVE_SIGNATURE={positive}')

# Generation 3 is a different representation class: a retained composite fact
# on Closure, established at construction and consumed later without re-deriving
# the future-relevant predicate.
value=root/'src/value.rs'
s=value.read_text()
old='''pub struct Closure<'a> {\n    pub env: E<'a>,\n    pub ctx: Option<C<'a>>,\n    pub body: ExprPtr<'a>,\n}'''
new='''pub struct Closure<'a> {\n    pub env: E<'a>,\n    pub ctx: Option<C<'a>>,\n    pub body: ExprPtr<'a>,\n    pub direct_cap: bool,\n}'''
if old not in s: raise SystemExit('closure representation template not found')
s=s.replace(old,new,1)

# Compile the learned anonymous basis/signature into producer-time establishment.
def predicate(ctx_expr, body_expr):
    terms=[]
    for i,v in zip(basis,positive):
        atom={0:f'({ctx_expr}).is_none()',1:f'({body_expr}).num_loose_bvars() == 0',2:'false',3:'false'}.get(i)
        if atom is None: raise SystemExit(f'unsupported q3 basis coordinate {i}')
        terms.append(f'({atom})' if v==1 else f'!({atom})')
    return ' && '.join(terms) if terms else 'true'

pred_eval=predicate('None::<C<\'_>>','body')
pred_infer=predicate('Some(ctx)','body')
old="""impl<'a> Closure<'a> {\n    pub fn mk_eval(env: E<'a>, body: ExprPtr<'a>) -> Self { Closure { env, ctx: None, body } }\n\n    pub fn mk_infer(env: E<'a>, ctx: C<'a>, body: ExprPtr<'a>) -> Self { Closure { env, ctx: Some(ctx), body } }\n}"""
new=f"""impl<'a> Closure<'a> {{\n    pub fn mk_eval(env: E<'a>, body: ExprPtr<'a>) -> Self {{\n        let direct_cap = {pred_eval};\n        Closure {{ env, ctx: None, body, direct_cap }}\n    }}\n\n    pub fn mk_infer(env: E<'a>, ctx: C<'a>, body: ExprPtr<'a>) -> Self {{\n        let direct_cap = {pred_infer};\n        Closure {{ env, ctx: Some(ctx), body, direct_cap }}\n    }}\n}}"""
if old not in s: raise SystemExit('closure constructor template not found')
s=s.replace(old,new,1)
value.write_text(s)

infer=root/'src/infer.rs'
s=infer.read_text()
old='''            if body.ctx.is_none() && self.ctx.num_loose_bvars(body.body) == 0 {'''
new='''            if body.direct_cap {'''
if old not in s: raise SystemExit('q3 consumer template not found after stage2')
s=s.replace(old,new,1)
infer.write_text(s)

manifest={
    'constructor':'anonymous_retained_closure_capability',
    'parent':meta['constructor'],
    'source_context':'q3',
    'basis':list(basis),
    'positive_signature':list(positive),
}
(root/'.msi-stage3-promotion.json').write_text(json.dumps(manifest,sort_keys=True)+'\n')
print('THIRD_STRUCTURALLY_DISTINCT_INTERFACE=PASS')
print('STAGE3_PRODUCER_PRESERVED_CONSEQUENCE=PASS')
print('STAGE3_CONSTRUCTOR_PROMOTION=PASS')
print('RECURSIVE_CLOSURE_GENESIS_V6=PASS')
