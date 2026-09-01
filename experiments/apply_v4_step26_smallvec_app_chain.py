#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / "src" / "eval.rs"
s = p.read_text()
old = """                let mut funs: Vec<ExprPtr<'t>> = Vec::with_capacity(count as usize);\n                funs.push(fun);\n                funs.push(f2);\n"""
new = """                let mut funs: smallvec::SmallVec<[ExprPtr<'t>; 8]> = smallvec::SmallVec::new();\n                funs.push(fun);\n                funs.push(f2);\n"""
if old not in s:
    raise SystemExit("target app-chain Vec block not found")
s = s.replace(old, new, 1)
p.write_text(s)
print("V4_STEP26_SMALLVEC_APP_CHAIN=YES")
