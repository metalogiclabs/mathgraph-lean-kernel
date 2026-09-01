#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / "src/eval.rs"
s = p.read_text()
old = '''                let first_fun = fun;
                let mut all_same = fun == f2;
                let mut count = 2u32;
                let mut cur = a2;
                let leaf_expr;
                loop {
                    match self.ctx.read_expr_ref(cur) {
                        &Expr::App { fun: fn3, arg: an3, .. } => {
                            count += 1;
                            if all_same && fn3 != first_fun {
                                all_same = false;
                            }
                            cur = an3;
                        }
                        _ => {
                            leaf_expr = cur;
                            break;
                        }
                    }
                }
                let mut result = self.eval(depth, env, leaf_expr);
                let nat_ext = self.nat_extension;
'''
new = '''                let first_fun = fun;
                let mut all_same = fun == f2;
                let mut count = 2u32;
                let mut funs: Option<Vec<ExprPtr<'t>>> = if all_same {
                    None
                } else {
                    Some(vec![fun, f2])
                };
                let mut cur = a2;
                let leaf_expr;
                loop {
                    match self.ctx.read_expr_ref(cur) {
                        &Expr::App { fun: fn3, arg: an3, .. } => {
                            count += 1;
                            if all_same && fn3 != first_fun {
                                all_same = false;
                                let mut fs = Vec::with_capacity(count as usize);
                                fs.extend(std::iter::repeat(first_fun).take((count - 1) as usize));
                                fs.push(fn3);
                                funs = Some(fs);
                            } else if let Some(fs) = funs.as_mut() {
                                fs.push(fn3);
                            }
                            cur = an3;
                        }
                        _ => {
                            leaf_expr = cur;
                            break;
                        }
                    }
                }
                let mut result = self.eval(depth, env, leaf_expr);
                let nat_ext = self.nat_extension;
'''
if old not in s:
    raise SystemExit("step26 first traversal anchor not found")
s = s.replace(old, new, 1)
old2 = '''                let mut funs: Vec<ExprPtr<'t>> = Vec::with_capacity(count as usize);
                funs.push(fun);
                funs.push(f2);
                let mut cur2 = a2;
                while let &Expr::App { fun: fn3, arg: an3, .. } = self.ctx.read_expr_ref(cur2) {
                    funs.push(fn3);
                    cur2 = an3;
                }
                let mut last_f_expr: Option<ExprPtr<'t>> = None;
'''
new2 = '''                let mut funs = funs.expect("heterogeneous app chain must collect functions");
                let mut last_f_expr: Option<ExprPtr<'t>> = None;
'''
if old2 not in s:
    raise SystemExit("step26 second traversal anchor not found")
s = s.replace(old2, new2, 1)
p.write_text(s)
print("V4_STEP26_SINGLE_PASS_HETERO_APP=YES")
