#!/usr/bin/env python3
from pathlib import Path
import sys

root=Path(sys.argv[1]); cand=sys.argv[2]
infer=root/'src/infer.rs'; s=infer.read_text()

# Reconstruct frozen accepted G1 + G2 + G3(final_field_pi) prefix.
old='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
new='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        if let Value::Sort { level, .. } = v { return *level; }\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
if old not in s: raise SystemExit('g1 site missing')
s=s.replace(old,new,1)
old='''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };'''
new='''        while let Some(arg) = args.pop() {\n            let fty_f = match fty {\n                Value::Pi { .. } => fty,\n                _ => self.force_all(depth, fty),\n            };\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };'''
if old not in s: raise SystemExit('g2 site missing')
s=s.replace(old,new,1)
old='''        match self.force_all(depth, cur) {\n            Value::Pi { domain, .. } => {'''
new='''        let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n        match cur_f {\n            Value::Pi { domain, .. } => {'''
if old not in s: raise SystemExit('g3 site missing')
s=s.replace(old,new,1)

def add_rigid(text):
    old='''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = self.force_all(depth, struct_ty);'''
    new='''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = match struct_ty {\n            Value::Rigid { .. } => struct_ty,\n            _ => self.force_all(depth, struct_ty),\n        };'''
    if old not in text: raise SystemExit('rigid site missing')
    return text.replace(old,new,1)

def add_param(text):
    old='''        for p in params.iter().take(num_params).copied() {\n            match self.force_all(depth, cur) {\n                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),\n                _ => panic!("ran out of param telescope in projection"),\n            }\n        }'''
    new='''        for p in params.iter().take(num_params).copied() {\n            let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n            match cur_f {\n                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),\n                _ => panic!("ran out of param telescope in projection"),\n            }\n        }'''
    if old not in text: raise SystemExit('param site missing')
    return text.replace(old,new,1)

def add_prior(text):
    old='''        for i in 0..idx {\n            match self.force_all(depth, cur) {'''
    new='''        for i in 0..idx {\n            let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n            match cur_f {'''
    if old not in text: raise SystemExit('prior site missing')
    return text.replace(old,new,1)

if cand=='g3': pass
elif cand=='param_prior': s=add_param(add_prior(s))
elif cand=='param_rigid': s=add_param(add_rigid(s))
elif cand=='prior_rigid': s=add_prior(add_rigid(s))
else: raise SystemExit(f'unknown candidate {cand}')

infer.write_text(s)
print(f'V9_CANDIDATE={cand}')
print('FROZEN_PREFIX=G1+G2+G3_FINAL_FIELD_PI')
print('PAIRWISE_OUTCOME_UNSEEN_AT_PREDICTION_TIME=YES')
