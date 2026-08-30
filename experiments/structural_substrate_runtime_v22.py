#!/usr/bin/env python3
from pathlib import Path
import re,sys
root=Path(sys.argv[1]);mode=sys.argv[2];expr=sys.argv[3] if len(sys.argv)>3 else '';pred=sys.argv[4] if len(sys.argv)>4 else ''
infer=root/'src/infer.rs';s=infer.read_text()
repls=[('''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }''','''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        if let Value::Sort { level, .. } = v { return *level; }\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''),('''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };''','''        while let Some(arg) = args.pop() {\n            let fty_f = match fty { Value::Pi { .. } => fty, _ => self.force_all(depth, fty) };\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };'''),('''        match self.force_all(depth, cur) {\n            Value::Pi { domain, .. } => {''','''        let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n        match cur_f {\n            Value::Pi { domain, .. } => {''')]
for a,b in repls:
 if a not in s:raise SystemExit('frozen prefix site missing')
 s=s.replace(a,b,1)
site='''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = self.force_all(depth, struct_ty);'''
if site not in s:raise SystemExit('projection site missing')
raw='''        use std::hash::{Hash, Hasher};
        let mut appgen_v22_p0: u64 = 0;
        let mut h0 = std::collections::hash_map::DefaultHasher::new();
        std::mem::discriminant(struct_ty).hash(&mut h0); appgen_v22_p0 = h0.finish();
        let mut appgen_v22_q0: u64 = 0;
        let mut appgen_v22_q1: u64 = 0;
        let mut appgen_v22_empty: u8 = 0;
        if let Value::Rigid { head, spine, .. } = struct_ty {
            let mut h1 = std::collections::hash_map::DefaultHasher::new();
            std::mem::discriminant(head).hash(&mut h1); appgen_v22_q0 = h1.finish();
            let mut h2 = std::collections::hash_map::DefaultHasher::new();
            std::mem::discriminant(&**spine).hash(&mut h2); appgen_v22_q1 = h2.finish();
            if matches!(**spine, crate::value::Spine::Empty) { appgen_v22_empty = 1; }
        }
        let appgen_v22_p3: u64 = depth as u64;
        let appgen_v22_closed: u8 = if struct_ty.is_closed() {1} else {0};
        let appgen_v22_canonical: u8 = if struct_ty.is_canonical() {1} else {0};'''
def var(path):return {'root.disc':'appgen_v22_p0','root.generated0.disc':'appgen_v22_q0','root.generated1.disc':'appgen_v22_q1','context.depth':'appgen_v22_p3'}[path]
def expr_rust(e):
 m=re.fullmatch(r'(?:neq0\()?((?:and|mod)\(shr\(([^,]+),(\d+)\),(1|2)\))\)?',e)
 if not m:raise SystemExit(f'bad expr {e!r}')
 inner,path,k,c=m.group(1),m.group(2),int(m.group(3)),int(m.group(4));v=var(path);base=f'((({v} >> {k}) & {c}) as u8)' if inner.startswith('and') else f'((({v} >> {k}) % {c}) as u8)';return f'(if {base} != 0 {{1u8}} else {{0u8}})' if e.startswith('neq0') else base
def pred_rust(p,g):
 if not p or p=='TRUE':return 'true'
 q={'empty':'appgen_v22_empty','closed':'appgen_v22_closed','canonical':'appgen_v22_canonical','g':g};return ' && '.join(f'({q[n]} == {int(v)}u8)' for n,v in (x.split('=') for x in p.split('&')))
if mode=='probe':new=f'''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n{raw}\n        let struct_ty_f = self.force_all(depth, struct_ty);\n        let appgen_v22_safe = std::ptr::eq(struct_ty, struct_ty_f);\n        eprintln!("APPGEN_V22 safe={{}} p0={{}} q0={{}} q1={{}} p3={{}} spine_empty={{}} closed={{}} canonical={{}}", if appgen_v22_safe {{1}} else {{0}}, appgen_v22_p0, appgen_v22_q0, appgen_v22_q1, appgen_v22_p3, appgen_v22_empty, appgen_v22_closed, appgen_v22_canonical);'''
elif mode in ('guard','broad'):
 g=expr_rust(expr);cond=pred_rust(pred,g);new=f'''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n{raw}\n        let appgen_v22_generated: u8 = {g};\n        let struct_ty_f = if {cond} {{ struct_ty }} else {{ self.force_all(depth, struct_ty) }};'''
elif mode=='g3':new=site
else:raise SystemExit('unknown mode')
s=s.replace(site,new,1);infer.write_text(s)
print(f'V22_RUNTIME_MODE={mode}');print(f'V22_RUNTIME_EXPR={expr or "NONE"}');print(f'V22_RUNTIME_PREDICATE={pred or "NONE"}');print('V22_INITIAL_SUBSTRATE=opaque_root+generic_facts+context');print('V22_SUBSTRATE_METAOP=decompose_active_variant_payload');print('V22_CELL_SEQUENCE_EXPOSED_TO_LEARNER=NO');print('V22_SLOT_FAMILY_EXPOSED_TO_LEARNER=NO');print('V22_SEMANTIC_NAMES_EXPOSED_TO_LEARNER=NO')
