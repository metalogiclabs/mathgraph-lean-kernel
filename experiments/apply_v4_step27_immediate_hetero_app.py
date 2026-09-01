#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / "src/eval.rs"
s = p.read_text()
old = '''            if let &Expr::App { fun: f2, arg: a2, .. } = self.ctx.read_expr_ref(arg) {
                let first_fun = fun;
                let mut all_same = fun == f2;
                let mut count = 2u32;
'''
new = '''            if let &Expr::App { fun: f2, arg: a2, .. } = self.ctx.read_expr_ref(arg) {
                // If the first two functions already differ, the chain is known heterogeneous.
                // Collect it once here instead of doing the homogeneous-detection walk and then
                // rescanning the same right-associated App spine.
                if fun != f2 {
                    let mut funs: Vec<ExprPtr<'t>> = Vec::with_capacity(8);
                    funs.push(fun);
                    funs.push(f2);
                    let mut cur = a2;
                    while let &Expr::App { fun: fn3, arg: an3, .. } = self.ctx.read_expr_ref(cur) {
                        funs.push(fn3);
                        cur = an3;
                    }
                    let mut result = self.eval(depth, env, cur);
                    let nat_ext = self.nat_extension;
                    let mut last_f_expr: Option<ExprPtr<'t>> = None;
                    let mut last_f_val: Option<V<'t>> = None;
                    while let Some(f_expr) = funs.pop() {
                        let f_val = if Some(f_expr) == last_f_expr {
                            last_f_val.unwrap()
                        } else {
                            let v = match self.ctx.read_expr_ref(f_expr) {
                                &Expr::Var { dbj_idx, .. } => {
                                    let v = env.lookup(dbj_idx).expect("eval: loose bvar");
                                    self.force_thunk(depth, v)
                                }
                                _ => self.eval(depth, env, f_expr),
                            };
                            last_f_expr = Some(f_expr);
                            last_f_val = Some(v);
                            v
                        };
                        if let Value::Rigid { head, spine, .. } = f_val {
                            let head_copy = *head;
                            let is_nat_ctor = nat_ext && matches!(head_copy, RigidHead::Ctor(_, _));
                            if !is_nat_ctor {
                                let sp = *spine;
                                let a = self.canonicalize_for_spine(result);
                                let ns = self.spine_snoc_hc(sp, Elim::app(a));
                                result = self.mk_rigid_hc(head_copy, ns);
                                continue;
                            }
                        }
                        result = self.apply(depth, f_val, result);
                    }
                    return result;
                }
                let first_fun = fun;
                let mut all_same = true;
                let mut count = 2u32;
'''
if old not in s:
    raise SystemExit("step27 anchor not found")
s = s.replace(old, new, 1)
p.write_text(s)
print("V4_STEP27_IMMEDIATE_HETERO_APP=YES")
