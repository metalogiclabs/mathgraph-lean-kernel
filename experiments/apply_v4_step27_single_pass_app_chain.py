#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / "src" / "eval.rs"
s = p.read_text()
old1 = """                let first_fun = fun;\n                let mut all_same = fun == f2;\n                let mut count = 2u32;\n                let mut cur = a2;\n                let leaf_expr;\n                loop {\n                    match self.ctx.read_expr_ref(cur) {\n                        &Expr::App { fun: fn3, arg: an3, .. } => {\n                            count += 1;\n                            if all_same && fn3 != first_fun {\n                                all_same = false;\n                            }\n                            cur = an3;\n                        }\n"""
new1 = """                let first_fun = fun;\n                let mut all_same = fun == f2;\n                let mut funs: Option<smallvec::SmallVec<[ExprPtr<'t>; 8]>> = if all_same {\n                    None\n                } else {\n                    let mut xs = smallvec::SmallVec::new();\n                    xs.push(fun);\n                    xs.push(f2);\n                    Some(xs)\n                };\n                let mut count = 2u32;\n                let mut cur = a2;\n                let leaf_expr;\n                loop {\n                    match self.ctx.read_expr_ref(cur) {\n                        &Expr::App { fun: fn3, arg: an3, .. } => {\n                            count += 1;\n                            if all_same && fn3 != first_fun {\n                                all_same = false;\n                                let mut xs = smallvec::SmallVec::new();\n                                xs.resize((count - 1) as usize, first_fun);\n                                xs.push(fn3);\n                                funs = Some(xs);\n                            } else if let Some(xs) = funs.as_mut() {\n                                xs.push(fn3);\n                            }\n                            cur = an3;\n                        }\n"""
if old1 not in s:
    raise SystemExit("first app-chain traversal block not found")
s = s.replace(old1, new1, 1)
old2 = """                let mut funs: smallvec::SmallVec<[ExprPtr<'t>; 8]> = smallvec::SmallVec::new();\n                funs.push(fun);\n                funs.push(f2);\n                let mut cur2 = a2;\n                while let &Expr::App { fun: fn3, arg: an3, .. } = self.ctx.read_expr_ref(cur2) {\n                    funs.push(fn3);\n                    cur2 = an3;\n                }\n"""
new2 = """                let mut funs = funs.expect(\"non-uniform app chain must have collected functions\");\n"""
if old2 not in s:
    raise SystemExit("second app-chain traversal block not found; apply Step26 first")
s = s.replace(old2, new2, 1)
p.write_text(s)
print("V4_STEP27_SINGLE_PASS_APP_CHAIN=YES")
