#!/usr/bin/env python3
from pathlib import Path
import sys

root=Path(sys.argv[1]); mask=int(sys.argv[2])
infer=root/'src/infer.rs'; s=infer.read_text()

# Frozen admitted prefix g1 -> g2.
old='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
new='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        if let Value::Sort { level, .. } = v { return *level; }\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
if old not in s: raise SystemExit('g1 site missing')
s=s.replace(old,new,1)
old='''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };'''
new='''        while let Some(arg) = args.pop() {\n            let (domain, body) = match fty {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => {\n                    let fty_f = self.force_all(depth, fty);\n                    match fty_f {\n                        Value::Pi { domain, body, .. } => (*domain, body),\n                        _ => panic!("expected a pi type"),\n                    }\n                }\n            };'''
if old not in s: raise SystemExit('g2 site missing')
s=s.replace(old,new,1)

PORTALS=['rigid_projection','param_pi','prior_field_pi','final_field_pi']

def replace_once(old,new,label):
    global s
    if old not in s: raise SystemExit(f'portal site missing: {label}')
    s=s.replace(old,new,1)

if mask & 1:
    replace_once('''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = self.force_all(depth, struct_ty);''','''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = match struct_ty {\n            Value::Rigid { .. } => struct_ty,\n            _ => self.force_all(depth, struct_ty),\n        };''','rigid_projection')
if mask & 2:
    replace_once('''        for p in params.iter().take(num_params).copied() {\n            match self.force_all(depth, cur) {\n                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),\n                _ => panic!("ran out of param telescope in projection"),\n            }\n        }''','''        for p in params.iter().take(num_params).copied() {\n            let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n            match cur_f {\n                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),\n                _ => panic!("ran out of param telescope in projection"),\n            }\n        }''','param_pi')
if mask & 4:
    replace_once('''        for i in 0..idx {\n            match self.force_all(depth, cur) {''','''        for i in 0..idx {\n            let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n            match cur_f {''','prior_field_pi')
if mask & 8:
    replace_once('''        match self.force_all(depth, cur) {\n            Value::Pi { domain, .. } => {''','''        let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n        match cur_f {\n            Value::Pi { domain, .. } => {''','final_field_pi')

infer.write_text(s)
active=[PORTALS[i] for i in range(4) if mask & (1<<i)]
print(f'HYPERGRAPH_NODE={mask:04b}')
print('ACTIVE_PORTALS=' + (','.join(active) if active else 'NONE'))
print('PREFIX_G1_G2=FROZEN')
