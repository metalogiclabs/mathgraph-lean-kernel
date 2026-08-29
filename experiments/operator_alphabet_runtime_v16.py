#!/usr/bin/env python3
from pathlib import Path
import re,sys

root=Path(sys.argv[1]); mode=sys.argv[2]
expr=sys.argv[3] if len(sys.argv)>3 else ''
predicate=sys.argv[4] if len(sys.argv)>4 else ''
infer=root/'src/infer.rs'; s=infer.read_text()

repls=[
('''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }''','''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        if let Value::Sort { level, .. } = v { return *level; }\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''),
('''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };''','''        while let Some(arg) = args.pop() {\n            let fty_f = match fty { Value::Pi { .. } => fty, _ => self.force_all(depth, fty) };\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };'''),
('''        match self.force_all(depth, cur) {\n            Value::Pi { domain, .. } => {''','''        let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n        match cur_f {\n            Value::Pi { domain, .. } => {''')]
for old,new in repls:
    if old not in s: raise SystemExit('frozen prefix site missing')
    s=s.replace(old,new,1)

site='''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = self.force_all(depth, struct_ty);'''
if site not in s: raise SystemExit('projection site missing')

raw='''        let mut appgen_v16_hash: u64 = 0;\n        let mut appgen_v16_empty: u8 = 0;\n        if let Value::Rigid { head, spine, .. } = struct_ty {\n            use std::hash::{Hash, Hasher};\n            let mut h = std::collections::hash_map::DefaultHasher::new();\n            std::mem::discriminant(head).hash(&mut h);\n            appgen_v16_hash = h.finish();\n            if matches!(**spine, crate::value::Spine::Empty) { appgen_v16_empty = 1; }\n        }\n        let appgen_v16_closed: u8 = if struct_ty.is_closed() {1} else {0};\n        let appgen_v16_canonical: u8 = if struct_ty.is_canonical() {1} else {0};'''

def expr_rust(e):
    if not e: return '0u8'
    m=re.fullmatch(r'(shift_mask|shift_mod2|mask_nonzero)\(disc_hash,(\d+)\)',e)
    if not m: raise SystemExit(f'bad expr {e!r}')
    op,k=m.group(1),int(m.group(2))
    if op=='shift_mask': return f'(((appgen_v16_hash >> {k}) & 1) as u8)'
    if op=='shift_mod2': return f'(((appgen_v16_hash >> {k}) % 2) as u8)'
    return f'(if (appgen_v16_hash & (1u64 << {k})) != 0 {{1u8}} else {{0u8}})'

def pred_rust(p,ge):
    if not p or p=='TRUE': return 'true'
    terms=[]
    for lit in p.split('&'):
        n,v=lit.split('=',1); v=int(v)
        if n=='empty': q='appgen_v16_empty'
        elif n=='closed': q='appgen_v16_closed'
        elif n=='canonical': q='appgen_v16_canonical'
        elif n=='g': q=ge
        else: raise SystemExit(f'bad predicate atom {n}')
        terms.append(f'({q} == {v}u8)')
    return ' && '.join(terms)

if mode=='probe':
    new=f'''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n{raw}\n        let struct_ty_f = self.force_all(depth, struct_ty);\n        let appgen_v16_safe = std::ptr::eq(struct_ty, struct_ty_f);\n        eprintln!("APPGEN_V16 safe={{}} disc_hash={{}} spine_empty={{}} closed={{}} canonical={{}}", if appgen_v16_safe {{1}} else {{0}}, appgen_v16_hash, appgen_v16_empty, appgen_v16_closed, appgen_v16_canonical);'''
elif mode in ('guard','broad'):
    ge=expr_rust(expr); cond=pred_rust(predicate,ge)
    new=f'''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n{raw}\n        let appgen_v16_generated: u8 = {ge};\n        let struct_ty_f = if {cond} {{ struct_ty }} else {{ self.force_all(depth, struct_ty) }};'''
elif mode=='g3': new=site
else: raise SystemExit('unknown mode')

s=s.replace(site,new,1); infer.write_text(s)
print(f'V16_RUNTIME_MODE={mode}')
print(f'V16_RUNTIME_EXPR={expr or "NONE"}')
print(f'V16_RUNTIME_PREDICATE={predicate or "NONE"}')
print('V16_SEMANTIC_VARIANT_NAMES_EXPOSED_TO_LEARNER=NO')
