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

raw='''        use std::hash::{Hash, Hasher};
        let mut appgen_v18_s0: u64 = 0;
        let mut hv = std::collections::hash_map::DefaultHasher::new();
        std::mem::discriminant(struct_ty).hash(&mut hv);
        appgen_v18_s0 = hv.finish();
        let mut appgen_v18_s1: u64 = 0;
        let mut appgen_v18_s2: u64 = 0;
        let mut appgen_v18_empty: u8 = 0;
        if let Value::Rigid { head, spine, .. } = struct_ty {
            let mut hh = std::collections::hash_map::DefaultHasher::new();
            std::mem::discriminant(head).hash(&mut hh);
            appgen_v18_s1 = hh.finish();
            let mut hs = std::collections::hash_map::DefaultHasher::new();
            std::mem::discriminant(&**spine).hash(&mut hs);
            appgen_v18_s2 = hs.finish();
            if matches!(**spine, crate::value::Spine::Empty) { appgen_v18_empty = 1; }
        }
        let appgen_v18_s3: u64 = depth as u64;
        let appgen_v18_closed: u8 = if struct_ty.is_closed() {1} else {0};
        let appgen_v18_canonical: u8 = if struct_ty.is_canonical() {1} else {0};'''

def expr_rust(e):
    if not e: return '0u8'
    m=re.fullmatch(r'(?:neq0\()?((?:and|mod)\(shr\((s[0-3]),(\d+)\),(1|2)\))\)?',e)
    if not m: raise SystemExit(f'bad expr {e!r}')
    inner,src,k,c=m.group(1),m.group(2),int(m.group(3)),int(m.group(4))
    v=f'appgen_v18_{src}'
    if inner.startswith('and'): base=f'((({v} >> {k}) & {c}) as u8)'
    else: base=f'((({v} >> {k}) % {c}) as u8)'
    return f'(if {base} != 0 {{1u8}} else {{0u8}})' if e.startswith('neq0') else base

def pred_rust(p,ge):
    if not p or p=='TRUE': return 'true'
    terms=[]
    for lit in p.split('&'):
        n,v=lit.split('='); v=int(v)
        q={'empty':'appgen_v18_empty','closed':'appgen_v18_closed','canonical':'appgen_v18_canonical','g':ge}[n]
        terms.append(f'({q} == {v}u8)')
    return ' && '.join(terms)

if mode=='probe':
    new=f'''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n{raw}\n        let struct_ty_f = self.force_all(depth, struct_ty);\n        let appgen_v18_safe = std::ptr::eq(struct_ty, struct_ty_f);\n        eprintln!("APPGEN_V18 safe={{}} s0={{}} s1={{}} s2={{}} s3={{}} spine_empty={{}} closed={{}} canonical={{}}", if appgen_v18_safe {{1}} else {{0}}, appgen_v18_s0, appgen_v18_s1, appgen_v18_s2, appgen_v18_s3, appgen_v18_empty, appgen_v18_closed, appgen_v18_canonical);'''
elif mode in ('guard','broad'):
    ge=expr_rust(expr); cond=pred_rust(predicate,ge)
    new=f'''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n{raw}\n        let appgen_v18_generated: u8 = {ge};\n        let struct_ty_f = if {cond} {{ struct_ty }} else {{ self.force_all(depth, struct_ty) }};'''
elif mode=='g3': new=site
else: raise SystemExit('unknown mode')
s=s.replace(site,new,1); infer.write_text(s)
print(f'V18_RUNTIME_MODE={mode}')
print(f'V18_RUNTIME_EXPR={expr or "NONE"}')
print(f'V18_RUNTIME_PREDICATE={predicate or "NONE"}')
print('V18_SOURCE_CHANNEL_NAMES_EXPOSED_TO_LEARNER=s0,s1,s2,s3')
print('V18_SEMANTIC_VARIANT_NAMES_EXPOSED_TO_LEARNER=NO')
