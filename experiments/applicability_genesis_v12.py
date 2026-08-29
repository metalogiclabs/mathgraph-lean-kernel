#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
mode = sys.argv[2]
allowed = set(filter(None, sys.argv[3].split(','))) if len(sys.argv) > 3 else set()
infer = root / 'src/infer.rs'
s = infer.read_text()

# Frozen accepted G1 + G2 + G3(final_field_pi) prefix.
repls = [
('''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }''',
'''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        if let Value::Sort { level, .. } = v { return *level; }\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''),
('''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };''',
'''        while let Some(arg) = args.pop() {\n            let fty_f = match fty { Value::Pi { .. } => fty, _ => self.force_all(depth, fty) };\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };'''),
('''        match self.force_all(depth, cur) {\n            Value::Pi { domain, .. } => {''',
'''        let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n        match cur_f {\n            Value::Pi { domain, .. } => {''')]
for old,new in repls:
    if old not in s: raise SystemExit('frozen prefix site missing')
    s=s.replace(old,new,1)

site='''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = self.force_all(depth, struct_ty);'''
if site not in s: raise SystemExit('projection site missing')

def tag_expr(v='struct_ty'):
    return f'''match {v} {{\n            Value::Rigid {{ head: RigidHead::BVar(..), .. }} => "bvar",\n            Value::Rigid {{ head: RigidHead::Axiom(..), .. }} => "axiom",\n            Value::Rigid {{ head: RigidHead::Ctor(..), .. }} => "ctor",\n            Value::Rigid {{ head: RigidHead::Recursor(..), .. }} => "recursor",\n            Value::Rigid {{ head: RigidHead::QuotConst(..), .. }} => "quotconst",\n            Value::Rigid {{ head: RigidHead::Inductive(..), .. }} => "inductive",\n            _ => "nonrigid",\n        }}'''

if mode == 'probe':
    new=f'''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let pre_tag = {tag_expr()};\n        let struct_ty_f = self.force_all(depth, struct_ty);\n        let unchanged = std::ptr::eq(struct_ty, struct_ty_f);\n        eprintln!("APPGEN_V12 pre={{}} unchanged={{}}", pre_tag, if unchanged {{1}} else {{0}});'''
elif mode in ('guard','broaden'):
    arms=[]
    patterns={
      'bvar':'RigidHead::BVar(..)', 'axiom':'RigidHead::Axiom(..)', 'ctor':'RigidHead::Ctor(..)',
      'recursor':'RigidHead::Recursor(..)', 'quotconst':'RigidHead::QuotConst(..)', 'inductive':'RigidHead::Inductive(..)'}
    for tag in sorted(allowed):
        if tag not in patterns: continue
        arms.append(f'Value::Rigid {{ head: {patterns[tag]}, .. }}')
    pat=' | '.join(arms) if arms else 'Value::Rigid { head: RigidHead::Inductive(..), .. } if false'
    new=f'''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = match struct_ty {{\n            {pat} => struct_ty,\n            _ => self.force_all(depth, struct_ty),\n        }};'''
else:
    raise SystemExit(f'unknown mode {mode}')

s=s.replace(site,new,1)
infer.write_text(s)
print(f'V12_MODE={mode}')
print('ALLOWED=' + ','.join(sorted(allowed)))
print('PREFIX=G1+G2+G3_FINAL_FIELD_PI')
