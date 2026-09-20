#!/usr/bin/env python3
from pathlib import Path

p=Path("src/infer.rs")
c=p.read_text()

# 1) Replace let-value infer+conv with expected-type checking.
old_let = """                if flag == Check {
                    self.infer_sort_of_v(flag, depth, env, ctx, binder_type);
                    let val_ty = self.infer_value(flag, depth, env, ctx, val);
                    assert!(self.conv_types_at(depth, dom, val_ty), "let def_eq failed");
                }
"""
new_let = """                if flag == Check {
                    self.infer_sort_of_v(flag, depth, env, ctx, binder_type);
                    self.check_expected_v(depth, env, ctx, val, dom, false);
                }
"""
if c.count(old_let) != 1:
    raise SystemExit(f"let anchor mismatch: {c.count(old_let)}")
c = c.replace(old_let, new_let, 1)

# 2) Replace application-argument infer+conv with expected-type checking.
old_app = """            if flag == Check {
                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);
                assert!(self.conv_types_at(depth, domain, arg_ty), "app arg def_eq failed");
            }
"""
new_app = """            if flag == Check {
                self.check_expected_v(depth, env, ctx, arg, domain, false);
            }
"""
if c.count(old_app) != 1:
    raise SystemExit(f"app anchor mismatch: {c.count(old_app)}")
c = c.replace(old_app, new_app, 1)

# 3) Replace theorem check with recursive expected-type path and fallback.
old_def = """    pub(crate) fn check_def_like_v(&mut self, d: &Declar<'t>, val: ExprPtr<'t>) {
        self.check_declar_info_v(d);
        let empty_env = self.empty_env();
        let empty_ctx = self.empty_ctx();
        let val_ty = self.infer_value(Check, 0, empty_env, empty_ctx, val);
        let declared = self.eval(0, empty_env, d.info().ty);
        assert!(self.def_eq_at(0, val_ty, declared), "def_eq failed");
    }
"""
new_def = """    fn check_expected_v(
        &mut self,
        depth: u32,
        env: E<'t>,
        ctx: C<'t>,
        e: ExprPtr<'t>,
        expected: V<'t>,
        use_defeq: bool,
    ) {
        if let Lambda { binder_type, body, .. } = self.ctx.read_expr(e) {
            let expected_f = self.force_all(depth, expected);
            if let Value::Pi { domain: expected_dom, body: expected_body, .. } = expected_f {
                self.infer_sort_of_v(Check, depth, env, ctx, binder_type);
                let dom = self.arg_value(depth, env, binder_type);
                assert!(self.conv_types_at(depth, *expected_dom, dom), "lambda binder def_eq failed");

                let fresh = self.mk_bvar_hc(depth, dom);
                let next_expected =
                    self.apply_closure(depth + 1, expected_body, fresh, Some(dom));
                let env2 = self.env_extend(env, fresh);
                let ctx2 = value::ctx_extend(self.arena, ctx, dom);

                self.check_expected_v(depth + 1, env2, ctx2, body, next_expected, use_defeq);
                return;
            }
        }

        let actual = self.infer_value(Check, depth, env, ctx, e);
        let ok = if use_defeq {
            self.def_eq_at(depth, actual, expected)
        } else {
            self.conv_types_at(depth, expected, actual)
        };
        assert!(ok, "expected type def_eq failed");
    }

    pub(crate) fn check_def_like_v(&mut self, d: &Declar<'t>, val: ExprPtr<'t>) {
        self.check_declar_info_v(d);
        let empty_env = self.empty_env();
        let empty_ctx = self.empty_ctx();

        if matches!(d, Declar::Theorem { .. }) {
            let declared = self.eval(0, empty_env, d.info().ty);
            self.check_expected_v(0, empty_env, empty_ctx, val, declared, true);
            return;
        }

        let val_ty = self.infer_value(Check, 0, empty_env, empty_ctx, val);
        let declared = self.eval(0, empty_env, d.info().ty);
        assert!(self.def_eq_at(0, val_ty, declared), "def_eq failed");
    }
"""
if c.count(old_def) != 1:
    raise SystemExit(f"def anchor mismatch: {c.count(old_def)}")
c = c.replace(old_def, new_def, 1)

p.write_text(c)
print("QCKN_EXPECTED_TYPE_RECURSIVE_V2_PATCH=PASS")
