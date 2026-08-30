#!/usr/bin/env python3
from pathlib import Path
import re,sys
root=Path(sys.argv[1]);mode=sys.argv[2];gen=sys.argv[3] if len(sys.argv)>3 else '';expr=sys.argv[4] if len(sys.argv)>4 else '';pred=sys.argv[5] if len(sys.argv)>5 else ''
infer=root/'src/infer.rs';s=infer.read_text()
repls=[('''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }''','''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        if let Value::Sort { level, .. } = v { return *level; }\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''),('''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };''','''        while let Some(arg) = args.pop() {\n            let fty_f = match fty { Value::Pi { .. } => fty, _ => self.force_all(depth, fty) };\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };'''),('''        match self.force_all(depth, cur) {\n            Value::Pi { domain, .. } => {''','''        let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n        match cur_f {\n            Value::Pi { domain, .. } => {''')]
for a,b in repls:
 if a not in s:raise SystemExit('prefix missing')
 s=s.replace(a,b,1)
site='''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = self.force_all(depth, struct_ty);'''
if site not in s:raise SystemExit('site missing')
raw='''        use std::hash::{Hash, Hasher};
        let mut hroot = std::collections::hash_map::DefaultHasher::new();
        std::mem::discriminant(struct_ty).hash(&mut hroot); let v27_root = hroot.finish();
        let mut v27_a0: u64 = 0; let mut v27_a1: u64 = 0; let mut v27_empty: u8 = 0;
        if let Value::Rigid { head, spine, .. } = struct_ty {
            let mut h0=std::collections::hash_map::DefaultHasher::new(); std::mem::discriminant(head).hash(&mut h0); v27_a0=h0.finish();
            let mut h1=std::collections::hash_map::DefaultHasher::new(); std::mem::discriminant(&**spine).hash(&mut h1); v27_a1=h1.finish();
            if matches!(**spine, crate::value::Spine::Empty) { v27_empty=1; }
        }
        let v27_closed:u8=if struct_ty.is_closed(){1}else{0}; let v27_canonical:u8=if struct_ty.is_canonical(){1}else{0};'''
def genvar(g):
 if g=='e0':return 'v27_root'
 if g=='u0;e0':return 'v27_a0'
 if g=='u1;e0':return 'v27_a1'
 raise SystemExit(f'bad generator {g}')
def exprrust(e,g):
 m=re.fullmatch(r'(?:neq0\()?((?:and|mod)\(shr\(GEN,(\d+)\),(1|2)\))\)?',e)
 if not m:raise SystemExit(f'bad expr {e}')
 inner,k,c=m.group(1),int(m.group(2)),int(m.group(3));v=genvar(g);base=f'((({v} >> {k}) & {c}) as u8)' if inner.startswith('and') else f'((({v} >> {k}) % {c}) as u8)';return f'(if {base} != 0 {{1u8}} else {{0u8}})' if e.startswith('neq0') else base
def predrust(p,g):
 if not p or p=='TRUE':return 'true'
 q={'empty':'v27_empty','closed':'v27_closed','canonical':'v27_canonical','g':g};return ' && '.join(f'({q[n]} == {int(v)}u8)' for n,v in (x.split('=') for x in p.split('&')))
if mode=='probe':new=f'''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n{raw}\n        let struct_ty_f=self.force_all(depth,struct_ty); let safe=std::ptr::eq(struct_ty,struct_ty_f);\n        eprintln!("ONLINEGEN_V27 safe={{}} root={{}} a0={{}} a1={{}} empty={{}} closed={{}} canonical={{}}",if safe{{1}}else{{0}},v27_root,v27_a0,v27_a1,v27_empty,v27_closed,v27_canonical);'''
elif mode in ('guard','broad'):
 g=exprrust(expr,gen);c=predrust(pred,g);new=f'''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n{raw}\n        let v27_generated:u8={g}; let struct_ty_f=if {c}{{struct_ty}}else{{self.force_all(depth,struct_ty)}};'''
elif mode=='base':new=site
else:raise SystemExit('mode')
s=s.replace(site,new,1);infer.write_text(s)
print(f'V27_RUNTIME_MODE={mode}');print(f'V27_GENERATOR={gen or "NONE"}');print('V27_PREMATERIALIZED_PROGRAM_OUTCOME_TABLE=NO');print('V27_COMPLETE_PROGRAM_TO_SOURCE_LOOKUP=NO');print('V27_PROGRAM_EXECUTED_BY_GENERIC_INTERPRETER=YES');print('V27_SEMANTIC_NAMES_EXPOSED=NO')
