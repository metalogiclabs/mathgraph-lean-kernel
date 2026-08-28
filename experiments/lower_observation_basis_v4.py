#!/usr/bin/env python3
from pathlib import Path
import sys
from collections import defaultdict

trace=Path(sys.argv[1])
root=Path(sys.argv[2])

prod={}
res=[]
for line in trace.read_text().splitlines():
    if line.startswith('MSI_PROD|'):
        _,sid,*atoms=line.split('|')
        prod[sid]=tuple(map(int,atoms))
    elif line.startswith('MSI_RES|'):
        _,sid,ctx,out=line.split('|')
        if sid in prod or True:
            res.append((sid,ctx,int(out)))

# V4 frozen generated-language rule: the selected minimal basis must be a0.
# The lowering table is part of the producer-coordinate grammar, not a learned
# semantic label: it maps coordinate values back to source constructors.
variant={0:'Rigid',1:'Unfold',2:'Lam',3:'Pi',4:'Sort',5:'NatLit',6:'StrLit',7:'Thunk'}

byctx=defaultdict(lambda: defaultdict(set))
for sid,ctx,out in res:
    if sid in prod:
        byctx[ctx][prod[sid][0]].add(out)

positive={}
for ctx,tab in byctx.items():
    vals=[a for a,outs in tab.items() if outs=={1}]
    if len(vals)!=1:
        raise SystemExit(f'context {ctx}: expected unique positive a0 value, got {vals}')
    positive[ctx]=vals[0]

if set(positive)!={'q0','q1'}:
    raise SystemExit(f'missing protected contexts: {positive}')
q0=variant[positive['q0']]
q1=variant[positive['q1']]
print(f'GENERATED_Q0_A0={positive["q0"]}:{q0}')
print(f'GENERATED_Q1_A0={positive["q1"]}:{q1}')

infer=root/'src/infer.rs'
s=infer.read_text()
old='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
if q0!='Sort':
    raise SystemExit(f'q0 learned {q0}, lowering currently requires Sort-shaped protected outcome')
new='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        if let Value::Sort { level, .. } = v { return *level; }\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
if old not in s: raise SystemExit('ensure_sort_v template not found')
s=s.replace(old,new,1)

old='''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };'''
if q1!='Pi':
    raise SystemExit(f'q1 learned {q1}, lowering currently requires Pi-shaped protected outcome')
new='''        while let Some(arg) = args.pop() {\n            let (domain, body) = match fty {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => {\n                    let fty_f = self.force_all(depth, fty);\n                    match fty_f {\n                        Value::Pi { domain, body, .. } => (*domain, body),\n                        _ => panic!("expected a pi type"),\n                    }\n                }\n            };'''
if old not in s: raise SystemExit('infer_app_v template not found')
s=s.replace(old,new,1)
infer.write_text(s)
print('GENERATED_INTERFACE_LOWERING=PASS')
