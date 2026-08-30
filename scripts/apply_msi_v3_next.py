#!/usr/bin/env python3
from pathlib import Path
import sys

p = Path(sys.argv[1] if len(sys.argv) > 1 else "src/infer.rs")
mode = sys.argv[2] if len(sys.argv) > 2 else "both"
s = p.read_text()

# Start from the certified compounded D state.
import subprocess
subprocess.run([sys.executable, str(Path(__file__).with_name('apply_msi_compounded_v3.py')), str(p)], check=True)
s = p.read_text()

if mode in ("struct", "both"):
    old = '''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = self.force_all(depth, struct_ty);\n        let struct_ty_is_prop = self.is_prop_type(depth, struct_ty_f);\n        let (ind_name, ind_levels, spine) = match struct_ty_f {\n            Value::Rigid { head: RigidHead::Inductive(n, ls), spine, .. } => (*n, *ls, *spine),\n            _ => panic!("projection structure type is not an inductive"),\n        };'''
    new = '''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = match struct_ty {\n            Value::Rigid { .. } => struct_ty,\n            _ => self.force_all(depth, struct_ty),\n        };\n        let struct_ty_is_prop = self.is_prop_type(depth, struct_ty_f);\n        let (ind_name, ind_levels, spine) = match struct_ty_f {\n            Value::Rigid { head: RigidHead::Inductive(n, ls), spine, .. } => (*n, *ls, *spine),\n            _ => panic!("projection structure type is not an inductive"),\n        };'''
    if s.count(old) != 1: raise SystemExit('struct site mismatch')
    s = s.replace(old, new, 1)
    print('APPLIED=struct_type_direct_rigid_fallback')

if mode in ("final", "both"):
    old = '''        match self.force_all(depth, cur) {\n            Value::Pi { domain, .. } => {\n                if struct_ty_is_prop && !self.is_prop_type(depth, domain) {\n                    panic!("projection of a non-proof field from a Prop structure")\n                }\n                *domain\n            }\n            _ => panic!("ran out of constructor telescope getting projection field"),\n        }'''
    new = '''        let cur_f = match cur {\n            Value::Pi { .. } => cur,\n            _ => self.force_all(depth, cur),\n        };\n        match cur_f {\n            Value::Pi { domain, .. } => {\n                if struct_ty_is_prop && !self.is_prop_type(depth, domain) {\n                    panic!("projection of a non-proof field from a Prop structure")\n                }\n                *domain\n            }\n            _ => panic!("ran out of constructor telescope getting projection field"),\n        }'''
    if s.count(old) != 1: raise SystemExit('final site mismatch')
    s = s.replace(old, new, 1)
    print('APPLIED=final_field_direct_pi_fallback')

p.write_text(s)
print('V3_NEXT_MODE='+mode)
