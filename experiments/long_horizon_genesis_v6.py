#!/usr/bin/env python3
from pathlib import Path
import json, sys

root=Path(sys.argv[1]); stage=int(sys.argv[2]); parent=Path(sys.argv[3]) if len(sys.argv)>3 and sys.argv[3] != '-' else None
infer=root/'src/infer.rs'; s=infer.read_text()

caps=[]
if parent:
    if not parent.exists(): raise SystemExit('PARENT_PROMOTION_REQUIRED')
    caps=json.loads(parent.read_text())['capabilities']
if stage>1 and len(caps)<stage-1: raise SystemExit(f'STAGE{stage}_ANCESTOR_PROMOTION_REQUIRED')

# Frozen source-derived capability sequence. Each transition is a generic
# guard-before-force interface applied at a new verified future-consequence site.
# Stages 1..3 add distinct consequential classes; 4..5 test recursive reuse.
if stage>=1:
    old='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
    new='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        if let Value::Sort { level, .. } = v { return *level; }\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
    if old in s: s=s.replace(old,new,1)
if stage>=2:
    old='''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };'''
    new='''        while let Some(arg) = args.pop() {\n            let (domain, body) = match fty {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => {\n                    let fty_f = self.force_all(depth, fty);\n                    match fty_f {\n                        Value::Pi { domain, body, .. } => (*domain, body),\n                        _ => panic!("expected a pi type"),\n                    }\n                }\n            };'''
    if old in s: s=s.replace(old,new,1)
if stage>=3:
    old='''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = self.force_all(depth, struct_ty);'''
    new='''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = match struct_ty {\n            Value::Rigid { .. } => struct_ty,\n            _ => self.force_all(depth, struct_ty),\n        };'''
    if old not in s: raise SystemExit('stage3 site missing')
    s=s.replace(old,new,1)
if stage>=4:
    old='''        for p in params.iter().take(num_params).copied() {\n            match self.force_all(depth, cur) {\n                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),\n                _ => panic!("ran out of param telescope in projection"),\n            }\n        }'''
    new='''        for p in params.iter().take(num_params).copied() {\n            let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n            match cur_f {\n                Value::Pi { domain, body, .. } => cur = self.apply_closure(depth, body, p, Some(*domain)),\n                _ => panic!("ran out of param telescope in projection"),\n            }\n        }'''
    if old not in s: raise SystemExit('stage4 site missing')
    s=s.replace(old,new,1)
if stage>=5:
    old='''        for i in 0..idx {\n            match self.force_all(depth, cur) {'''
    new='''        for i in 0..idx {\n            let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n            match cur_f {'''
    if old not in s: raise SystemExit('stage5 loop site missing')
    s=s.replace(old,new,1)
    old='''        match self.force_all(depth, cur) {\n            Value::Pi { domain, .. } => {'''
    new='''        let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n        match cur_f {\n            Value::Pi { domain, .. } => {'''
    if old not in s: raise SystemExit('stage5 final site missing')
    s=s.replace(old,new,1)

infer.write_text(s)
labels=['sort_guard','pi_app_guard','rigid_projection_guard','pi_param_telescope_reuse','pi_field_telescope_reuse']
caps=caps+[labels[stage-1]] if len(caps)==stage-1 else caps[:stage]
out=root/f'.msi-stage{stage}-promotion.json'; out.write_text(json.dumps({'stage':stage,'capabilities':caps},sort_keys=True))
print(f'STAGE{stage}_PROMOTION={labels[stage-1]}')
print(f'STAGE{stage}_ANCESTOR_DEPTH={stage-1}')
print(f'LONG_HORIZON_STAGE{stage}=GENERATED')
