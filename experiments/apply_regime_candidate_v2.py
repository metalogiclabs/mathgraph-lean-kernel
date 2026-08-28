from __future__ import annotations

import pathlib
import sys

mode = sys.argv[1]
root = pathlib.Path(sys.argv[2])
p = root / "src" / "infer.rs"
s = p.read_text()

if mode not in {"cold", "s", "p", "sp"}:
    raise SystemExit(f"unknown mode {mode}")

if mode == "cold":
    raise SystemExit(0)

if "s" in mode:
    old = '''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
    new = '''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        if let Value::Sort { level, .. } = v {\n            return *level;\n        }\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
    if old not in s:
        raise SystemExit("ensure_sort_v pattern not found")
    s = s.replace(old, new, 1)

    old = '''            if flag == Check {\n                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);\n                assert!(self.conv_types_at(depth, domain, arg_ty), "app arg def_eq failed");\n            }'''
    new = '''            if flag == Check {\n                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);\n                let direct = match (domain, arg_ty) {\n                    (Value::Sort { level: a, .. }, Value::Sort { level: b, .. }) => *a == *b,\n                    _ => false,\n                };\n                assert!(direct || self.conv_types_at(depth, domain, arg_ty), "app arg def_eq failed");\n            }'''
    if old not in s:
        raise SystemExit("app check pattern not found")
    s = s.replace(old, new, 1)

    old = '''                    let val_ty = self.infer_value(flag, depth, env, ctx, val);\n                    assert!(self.conv_types_at(depth, dom, val_ty), "let def_eq failed");'''
    new = '''                    let val_ty = self.infer_value(flag, depth, env, ctx, val);\n                    let direct = match (dom, val_ty) {\n                        (Value::Sort { level: a, .. }, Value::Sort { level: b, .. }) => *a == *b,\n                        _ => false,\n                    };\n                    assert!(direct || self.conv_types_at(depth, dom, val_ty), "let def_eq failed");'''
    if old not in s:
        raise SystemExit("let check pattern not found")
    s = s.replace(old, new, 1)

if "p" in mode:
    old = '''            let fty_f = self.force_all(depth, fty);'''
    new = '''            let fty_f = match fty {\n                Value::Pi { .. } => fty,\n                _ => self.force_all(depth, fty),\n            };'''
    if old not in s:
        raise SystemExit("app force pattern not found")
    s = s.replace(old, new, 1)

p.write_text(s)
print(f"REGIME_CANDIDATE={mode}")
