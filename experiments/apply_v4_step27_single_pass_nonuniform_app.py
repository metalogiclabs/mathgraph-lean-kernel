#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / "src" / "eval.rs"
s = p.read_text()
old = """                let first_fun = fun;
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
"""
new = """                let first_fun = fun;
                let mut all_same = fun == f2;
                let mut count = 2u32;
                let mut nonuniform_funs: Option<smallvec::SmallVec<[ExprPtr<'t>; 8]>> = if all_same {
                    None
                } else {
                    let mut v = smallvec::SmallVec::new();
                    v.push(fun);
                    v.push(f2);
                    Some(v)
                };
                let mut cur = a2;
                let leaf_expr;
                loop {
                    match self.ctx.read_expr_ref(cur) {
                        &Expr::App { fun: fn3, arg: an3, .. } => {
                            count += 1;
                            if all_same && fn3 != first_fun {
                                all_same = false;
                                let mut v = smallvec::SmallVec::new();
                                for _ in 0..(count - 1) {
                                    v.push(first_fun);
                                }
                                v.push(fn3);
                                nonuniform_funs = Some(v);
                            } else if !all_same {
                                nonuniform_funs.as_mut().unwrap().push(fn3);
                            }
                            cur = an3;
                        }
                        _ => {
                            leaf_expr = cur;
                            break;
                        }
                    }
                }
"""
if old not in s:
    raise SystemExit("first-pass app scan block not found")
s = s.replace(old, new, 1)
old2 = """                let mut funs: smallvec::SmallVec<[ExprPtr<'t>; 8]> = smallvec::SmallVec::new();
                funs.push(fun);
                funs.push(f2);
                let mut cur2 = a2;
                while let &Expr::App { fun: fn3, arg: an3, .. } = self.ctx.read_expr_ref(cur2) {
                    funs.push(fn3);
                    cur2 = an3;
                }
"""
new2 = """                let mut funs = nonuniform_funs.expect("non-uniform app chain");
"""
if old2 not in s:
    raise SystemExit("second-pass app collection block not found")
s = s.replace(old2, new2, 1)
p.write_text(s)
print("V4_STEP27_SINGLE_PASS_NONUNIFORM_APP=YES")
