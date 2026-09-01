#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / "src" / "eval.rs"
s = p.read_text()
old = """                let mut last_f_expr: Option<ExprPtr<'t>> = None;\n                let mut last_f_val: Option<V<'t>> = None;\n                while let Some(f_expr) = funs.pop() {\n"""
new = """                let mut last_f_expr: Option<ExprPtr<'t>> = None;\n                let mut last_f_val: Option<V<'t>> = None;\n                for &f_expr in funs.iter().rev() {\n"""
if old not in s:
    raise SystemExit("Step28 target not found; apply Step26 first")
s = s.replace(old, new, 1)
p.write_text(s)
print("V4_STEP28_REVERSE_ITER_APP_CHAIN=YES")
