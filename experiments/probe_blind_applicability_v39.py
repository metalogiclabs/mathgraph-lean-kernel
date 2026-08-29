#!/usr/bin/env python3
from pathlib import Path

p = Path('src/infer.rs')
s = p.read_text()
old = '''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = self.force_all(depth, struct_ty);'''
if old not in s:
    raise SystemExit('projection site missing')
new = '''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let msi_v39_pre = match struct_ty {\n            Value::Rigid { head: RigidHead::BVar(..), .. } => "p0",\n            Value::Rigid { head: RigidHead::Axiom(..), .. } => "p1",\n            Value::Rigid { head: RigidHead::Ctor(..), .. } => "p2",\n            Value::Rigid { head: RigidHead::Recursor(..), .. } => "p3",\n            Value::Rigid { head: RigidHead::QuotConst(..), .. } => "p4",\n            Value::Rigid { head: RigidHead::Inductive(..), .. } => "p5",\n            _ => "p6",\n        };\n        let struct_ty_f = self.force_all(depth, struct_ty);\n        let msi_v39_unchanged = std::ptr::eq(struct_ty, struct_ty_f);\n        eprintln!("MSI_V39_APP pre={} unchanged={}", msi_v39_pre, if msi_v39_unchanged {1} else {0});'''
s = s.replace(old, new, 1)
p.write_text(s)
print('applied MSI blind applicability probe v39')
