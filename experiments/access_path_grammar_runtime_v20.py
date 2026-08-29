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
        let mut appgen_v20_p0: u64 = 0;
        let mut h0 = std::collections::hash_map::DefaultHasher::new();
        std::mem::discriminant(struct_ty).hash(&mut h0); appgen_v20_p0 = h0.finish();
        let mut appgen_v20_p1: u64 = 0;
        let mut appgen_v20_p2: u64 = 0;
        let mut appgen_v20_empty: u8 = 0;
        if let Value::Rigid { head, spine, .. } = struct_ty {
            let mut h1 = std::collections::hash_map::DefaultHasher::new();
            std::mem::discriminant(head).hash(&mut h1); appgen_v20_p1 = h1.finish();
            let mut h2 = std::collections::hash_map::DefaultHasher::new();
            std::mem::discriminant(&**spine).hash(&mut h2); appgen_v20_p2 = h2.finish();
            if matches!(**spine, crate::value::Spine::Empty) { appgen_v20_empty = 1; }
        }
        let appgen_v20_p3: u64 = depth as u64;
        let appgen_v20_closed: u8 = if struct_ty.is_closed() {1} else {0};
        let appgen_v20_canonical: u8 = if struct_ty.is_canonical() {1} else {0};'''

def path_var(path):
    return {
      'root.disc':'appgen_v20_p0',
      'root.rigid.slot0.disc':'appgen_v20_p1',
      'root.rigid.slot1.disc':'appgen_v20_p2',
      'root.rigid.spine.disc':'appgen_v20_p2',
      'context.depth':'appgen_v20_p3'}[path]

def expr_rust(e):
    if not e: return '0u8'
    m=re.fullmatch(r'(?:neq0\()?((?:and|mod)\(shr\(([^,]+),(\d+)\),(1|2)\))\)?',e)
    if not m: raise SystemExit(f'bad expr {e!r}')
    inner,path,k,c=m.group(1),m.group(2),int(m.group(3)),int(m.group(4)); v=path_var(path)
    base=f'((({v} >> {k}) & {c}) as u8)' if inner.startswith('and') else f'((({v} >> {k}) % {c}) as u8)'
    return f'(if {base} != 0 {{1u8}} else {{0u8}})' if e.startswith('neq0') else base

def pred_rust(p,ge):
    if not p or p=='TRUE': return 'true'
    terms=[]
    for lit in p.split('&'):
        n,v=lit.split('='); v=int(v)
        q={'empty':'appgen_v20_empty','closed':'appgen_v20_closed','canonical':'appgen_v20_canonical','g':ge}[n]
        terms.append(f'({q} == {v}u8)')
    return ' && '.join(terms)
if mode=='probe':
    new=f'''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n{raw}\n        let struct_ty_f = self.force_all(depth, struct_ty);\n        let appgen_v20_safe = std::ptr::eq(struct_ty, struct_ty_f);\n        eprintln!("APPGEN_V20 safe={{}} p0={{}} p1={{}} p2={{}} p3={{}} spine_empty={{}} closed={{}} canonical={{}}", if appgen_v20_safe {{1}} else {{0}}, appgen_v20_p0, appgen_v20_p1, appgen_v20_p2, appgen_v20_p3, appgen_v20_empty, appgen_v20_closed, appgen_v20_canonical);'''
elif mode in ('guard','broad'):
    ge=expr_rust(expr); cond=pred_rust(predicate,ge)
    new=f'''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n{raw}\n        let appgen_v20_generated: u8 = {ge};\n        let struct_ty_f = if {cond} {{ struct_ty }} else {{ self.force_all(depth, struct_ty) }};'''
elif mode=='g3': new=site
else: raise SystemExit('unknown mode')
s=s.replace(site,new,1); infer.write_text(s)
print(f'V20_RUNTIME_MODE={mode}')
print(f'V20_RUNTIME_EXPR={expr or "NONE"}')
print(f'V20_RUNTIME_PREDICATE={predicate or "NONE"}')
print('V20_INITIAL_PATH_GRAMMAR=root.disc,root.rigid.spine.disc,context.depth')
print('V20_SELECTOR_EXTENSION_GENERATOR=slot(i),i=0..1')
print('V20_SEMANTIC_VARIANT_NAMES_EXPOSED_TO_LEARNER=NO')
