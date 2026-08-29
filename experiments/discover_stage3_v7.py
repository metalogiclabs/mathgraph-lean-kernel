#!/usr/bin/env python3
from pathlib import Path
import sys

root=Path(sys.argv[1]); cand=sys.argv[2]
infer=root/'src/infer.rs'; s=infer.read_text()

# Reconstruct the already-admitted g1->g2 developmental prefix exactly.
old='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
new='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        if let Value::Sort { level, .. } = v { return *level; }\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
if old not in s: raise SystemExit('g1 site missing')
s=s.replace(old,new,1)
old='''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };'''
new='''        while let Some(arg) = args.pop() {\n            let (domain, body) = match fty {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => {\n                    let fty_f = self.force_all(depth, fty);\n                    match fty_f {\n                        Value::Pi { domain, body, .. } => (*domain, body),\n                        _ => panic!("expected a pi type"),\n                    }\n                }\n            };'''
if old not in s: raise SystemExit('g2 site missing')
s=s.replace(old,new,1)

# Frozen candidate family: every remaining force/shape boundary in infer_proj_v
# for which the already-promoted generic guard-before-force operator can be
# instantiated without adding a new semantic oracle. No candidate is privileged.
if cand=='g2':
    pass
elif cand=='rigid_projection':
    old='''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = self.force_all(depth, struct_ty);'''
    new='''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = match struct_ty {\n            Value::Rigid { .. } => struct_ty,\n            _ => self.force_all(depth, struct_ty),\n        };'''
    if old not in s: raise SystemExit('candidate site missing: rigid_projection')
    s=s.replace(old,new,1)
elif cand=='param_pi':
    old='''        for p in params.iter().take(num_params).copied() {\n            match self.force_all(depth, cur) {\n                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),\n                _ => panic!("ran out of param telescope in projection"),\n            }\n        }'''
    new='''        for p in params.iter().take(num_params).copied() {\n            let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n            match cur_f {\n                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),\n                _ => panic!("ran out of param telescope in projection"),\n            }\n        }'''
    if old not in s: raise SystemExit('candidate site missing: param_pi')
    s=s.replace(old,new,1)
elif cand=='prior_field_pi':
    old='''        for i in 0..idx {\n            match self.force_all(depth, cur) {'''
    new='''        for i in 0..idx {\n            let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n            match cur_f {'''
    if old not in s: raise SystemExit('candidate site missing: prior_field_pi')
    s=s.replace(old,new,1)
elif cand=='final_field_pi':
    old='''        match self.force_all(depth, cur) {\n            Value::Pi { domain, .. } => {'''
    new='''        let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n        match cur_f {\n            Value::Pi { domain, .. } => {'''
    if old not in s: raise SystemExit('candidate site missing: final_field_pi')
    s=s.replace(old,new,1)
else:
    raise SystemExit(f'unknown candidate {cand}')

infer.write_text(s)
print(f'STAGE3_CANDIDATE={cand}')
print('STAGE3_PREFIX_G1_G2=RECONSTRUCTED')
print('STAGE3_FROZEN_CANDIDATE_FAMILY=rigid_projection,param_pi,prior_field_pi,final_field_pi')
