#!/usr/bin/env python3
from __future__ import annotations
import json,subprocess,sys
from pathlib import Path

if len(sys.argv)!=3: raise SystemExit('usage: apply_v39 SELECTION MODE')
sel=json.loads(Path(sys.argv[1]).read_text())
mode=sys.argv[2]
if mode not in {'local','shared','gated','ungated','ablate'}: raise SystemExit('bad mode')
# First materialize the independently selected retained semantic capability.
v38_mode={'local':'local','shared':'shared','gated':'shared','ungated':'shared','ablate':'ablate'}[mode]
script=Path(__file__).with_name('apply_blind_kernel_interface_v38.py')
cp=subprocess.run([sys.executable,str(script),sys.argv[1],v38_mode])
if cp.returncode: raise SystemExit(cp.returncode)
if mode in {'local','shared','ablate'}:
    print('V39_MODE='+mode+' applicability=baseline')
    raise SystemExit(0)

p=Path('src/infer.rs'); s=p.read_text()
old='''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = self.force_all(depth, struct_ty);'''
if old not in s: raise SystemExit('projection site missing after interface materialization')
patterns={
 'bvar':'RigidHead::BVar(..)','axiom':'RigidHead::Axiom(..)','ctor':'RigidHead::Ctor(..)',
 'recursor':'RigidHead::Recursor(..)','quotconst':'RigidHead::QuotConst(..)','inductive':'RigidHead::Inductive(..)'}
if mode=='gated':
    tag=sel['winner_applicability_materializer']
    if tag not in patterns: raise SystemExit('selected applicability class is not a rigid reusable class: '+tag)
    pat=patterns[tag]
    new=f'''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = match struct_ty {{\n            Value::Rigid {{ head: {pat}, .. }} => struct_ty,\n            _ => self.force_all(depth, struct_ty),\n        }};'''
else:
    # Deliberately over-generalized reuse: tests whether learned scope matters.
    new='''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = match struct_ty {\n            Value::Rigid { .. } => struct_ty,\n            _ => self.force_all(depth, struct_ty),\n        };'''
s=s.replace(old,new,1); p.write_text(s)
print('V39_MODE='+mode+' capability='+sel['winner_materializer']+' applicability='+sel['winner_applicability_materializer'])
