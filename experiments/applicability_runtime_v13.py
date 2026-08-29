#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
mode = sys.argv[2]
predicate = sys.argv[3] if len(sys.argv) > 3 else ''
infer = root / 'src/infer.rs'
s = infer.read_text()

# Frozen accepted G1 + G2 + G3(final_field_pi) prefix from V12.
repls = [
('''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }''',
'''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        if let Value::Sort { level, .. } = v { return *level; }\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''),
('''        while let Some(arg) = args.pop() {\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };''',
'''        while let Some(arg) = args.pop() {\n            let fty_f = match fty { Value::Pi { .. } => fty, _ => self.force_all(depth, fty) };\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };'''),
('''        match self.force_all(depth, cur) {\n            Value::Pi { domain, .. } => {''',
'''        let cur_f = match cur { Value::Pi { .. } => cur, _ => self.force_all(depth, cur) };\n        match cur_f {\n            Value::Pi { domain, .. } => {''')]
for old,new in repls:
    if old not in s:
        raise SystemExit('frozen prefix site missing')
    s=s.replace(old,new,1)

site='''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = self.force_all(depth, struct_ty);'''
if site not in s:
    raise SystemExit('projection site missing')

# Anonymous feature extractor: no RigidHead variant names are inspected.  We hash only
# std::mem::Discriminant, then expose its low 12 bits plus three generic Value facts.
# The learner receives only f0..f14.
feature_block = '''        let mut appgen_v13_bits: u16 = 0;\n        if let Value::Rigid { head, spine, .. } = struct_ty {\n            use std::hash::{Hash, Hasher};\n            let mut h = std::collections::hash_map::DefaultHasher::new();\n            std::mem::discriminant(head).hash(&mut h);\n            let d = h.finish();\n            for i in 0..12 {\n                if ((d >> i) & 1) != 0 { appgen_v13_bits |= 1u16 << i; }\n            }\n            if matches!(**spine, crate::value::Spine::Empty) { appgen_v13_bits |= 1u16 << 12; }\n            if struct_ty.is_closed() { appgen_v13_bits |= 1u16 << 13; }\n            if struct_ty.is_canonical() { appgen_v13_bits |= 1u16 << 14; }\n        }'''

def pred_expr(text: str) -> str:
    if not text or text == 'TRUE':
        return 'true'
    terms=[]
    for lit in text.split('&'):
        if not lit.startswith('f') or '=' not in lit:
            raise SystemExit(f'bad predicate literal {lit!r}')
        lhs,val=lit.split('=',1)
        idx=int(lhs[1:]); bit=int(val)
        if idx < 0 or idx > 14 or bit not in (0,1):
            raise SystemExit(f'bad predicate literal {lit!r}')
        e=f'((appgen_v13_bits >> {idx}) & 1) == {bit}'
        terms.append(e)
    return ' && '.join(terms)

if mode == 'probe':
    new=f'''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n{feature_block}\n        let struct_ty_f = self.force_all(depth, struct_ty);\n        let appgen_v13_safe = std::ptr::eq(struct_ty, struct_ty_f);\n        eprint!("APPGEN_V13 safe={{}}", if appgen_v13_safe {{1}} else {{0}});\n        for i in 0..15 {{ eprint!(" f{{}}={{}}", i, (appgen_v13_bits >> i) & 1); }}\n        eprintln!();'''
elif mode in ('guard','broad'):
    cond=pred_expr(predicate)
    new=f'''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n{feature_block}\n        let struct_ty_f = if {cond} {{ struct_ty }} else {{ self.force_all(depth, struct_ty) }};'''
elif mode == 'g3':
    new=site
else:
    raise SystemExit(f'unknown mode {mode}')

s=s.replace(site,new,1)
infer.write_text(s)
print(f'V13_RUNTIME_MODE={mode}')
print(f'V13_RUNTIME_PREDICATE={predicate or "NONE"}')
print('V13_FEATURE_LANGUAGE=12_DISCRIMINANT_HASH_BITS+SPINE_EMPTY+CLOSED+CANONICAL')
print('V13_SEMANTIC_VARIANT_NAMES_EXPOSED_TO_LEARNER=NO')
