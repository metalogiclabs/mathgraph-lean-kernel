#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / "src" / "eval.rs"
s = p.read_text()
old = """            let f = self.eval(depth, env, fun);\n            let a = self.eval(depth, env, arg);\n"""
new = """            let f = match self.ctx.read_expr_ref(fun) {\n                &Expr::Var { dbj_idx, .. } => {\n                    let v = env.lookup(dbj_idx).expect(\"eval: loose bvar\");\n                    self.force_thunk(depth, v)\n                }\n                _ => self.eval(depth, env, fun),\n            };\n            let a = self.eval(depth, env, arg);\n"""
if old not in s:
    raise SystemExit("non-nested App eval block not found")
s = s.replace(old, new, 1)
p.write_text(s)
print("V4_STEP28_NON_NESTED_APP_VAR_FASTPATH=YES")
