#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / "src" / "eval.rs"
s = p.read_text()
needle = """                let mut funs: smallvec::SmallVec<[ExprPtr<'t>; 8]> = smallvec::SmallVec::new();\n"""
insert = """                if count == 2 {\n                    for f_expr in [f2, fun] {\n                        let f_val = match self.ctx.read_expr_ref(f_expr) {\n                            &Expr::Var { dbj_idx, .. } => {\n                                let v = env.lookup(dbj_idx).expect(\"eval: loose bvar\");\n                                self.force_thunk(depth, v)\n                            }\n                            _ => self.eval(depth, env, f_expr),\n                        };\n                        if let Value::Rigid { head, spine, .. } = f_val {\n                            let head_copy = *head;\n                            let is_nat_ctor = nat_ext && matches!(head_copy, RigidHead::Ctor(_, _));\n                            if !is_nat_ctor {\n                                let sp = *spine;\n                                let a = self.canonicalize_for_spine(result);\n                                let ns = self.spine_snoc_hc(sp, Elim::app(a));\n                                result = self.mk_rigid_hc(head_copy, ns);\n                                continue;\n                            }\n                        }\n                        result = self.apply(depth, f_val, result);\n                    }\n                    return result;\n                }\n\n                let mut funs: smallvec::SmallVec<[ExprPtr<'t>; 8]> = smallvec::SmallVec::new();\n"""
if needle not in s:
    raise SystemExit("Step26 SmallVec app-chain block not found")
s = s.replace(needle, insert, 1)
p.write_text(s)
print("V4_STEP28_LEN2_APP_CHAIN_FASTPATH=YES")
