#!/usr/bin/env python3
from pathlib import Path

p=Path("src/infer.rs")
c=p.read_text()

old="""    pub(crate) fn check_def_like_v(&mut self, d: &Declar<'t>, val: ExprPtr<'t>) {
        self.check_declar_info_v(d);
        let empty_env = self.empty_env();
        let empty_ctx = self.empty_ctx();
        let val_ty = self.infer_value(Check, 0, empty_env, empty_ctx, val);
        let declared = self.eval(0, empty_env, d.info().ty);
        assert!(self.def_eq_at(0, val_ty, declared), "def_eq failed");
    }
"""
new="""    fn check_expected_prefix(
        &mut self,
        mut depth: u32,
        mut env: E<'t>,
        mut ctx: C<'t>,
        mut proof: ExprPtr<'t>,
        mut expected: V<'t>,
    ) {
        loop {
            let (binder_type, body) = match self.ctx.read_expr(proof) {
                Lambda { binder_type, body, .. } => (binder_type, body),
                _ => {
                    let val_ty = self.infer_value(Check, depth, env, ctx, proof);
                    assert!(self.def_eq_at(depth, val_ty, expected), "def_eq failed");
                    return;
                }
            };

            let expected_f = self.force_all(depth, expected);
            let (expected_dom, expected_body) = match expected_f {
                Value::Pi { domain, body, .. } => (*domain, *body),
                _ => {
                    let val_ty = self.infer_value(Check, depth, env, ctx, proof);
                    assert!(self.def_eq_at(depth, val_ty, expected), "def_eq failed");
                    return;
                }
            };

            // Preserve the same binder well-formedness check performed by
            // infer_value(Check, ..., Lambda).
            self.infer_sort_of_v(Check, depth, env, ctx, binder_type);
            let dom = self.arg_value(depth, env, binder_type);

            // This is the domain comparison that ordinary Pi definitional
            // equality would perform after synthesizing the whole lambda type.
            assert!(self.conv_types_at(depth, dom, expected_dom), "lambda binder def_eq failed");

            let fresh = self.mk_bvar_hc(depth, dom);
            let next_expected = self.apply_closure(depth + 1, &expected_body, fresh, Some(dom));
            env = self.env_extend(env, fresh);
            ctx = value::ctx_extend(self.arena, ctx, dom);
            proof = body;
            expected = next_expected;
            depth += 1;
        }
    }

    pub(crate) fn check_def_like_v(&mut self, d: &Declar<'t>, val: ExprPtr<'t>) {
        self.check_declar_info_v(d);
        let empty_env = self.empty_env();
        let empty_ctx = self.empty_ctx();

        if matches!(d, Declar::Theorem { .. })
            && matches!(self.ctx.read_expr(val), Lambda { .. })
        {
            let declared = self.eval(0, empty_env, d.info().ty);
            self.check_expected_prefix(0, empty_env, empty_ctx, val, declared);
            return;
        }

        let val_ty = self.infer_value(Check, 0, empty_env, empty_ctx, val);
        let declared = self.eval(0, empty_env, d.info().ty);
        assert!(self.def_eq_at(0, val_ty, declared), "def_eq failed");
    }
"""
if c.count(old)!=1:
    raise SystemExit(f"expected anchor once, got {c.count(old)}")
p.write_text(c.replace(old,new,1))
print("QCKN_EXPECTED_TYPE_PREFIX_PATCH=PASS")
