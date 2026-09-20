#!/usr/bin/env python3
from pathlib import Path

p=Path("src/infer.rs")
c=p.read_text()

old = """        let r = match self.ctx.read_expr(e) {
            App { .. } => self.infer_app_v(flag, depth, env, ctx, e),
            Lambda { binder_type, body, .. } => {
                let dom = self.arg_value(depth, env, binder_type);
                let mut body_ty = None;
                if flag == Check {
                    self.infer_sort_of_v(flag, depth, env, ctx, binder_type);
                    let fresh = self.mk_bvar_hc(depth, dom);
                    let env2 = self.env_extend(env, fresh);
                    let ctx2 = value::ctx_extend(self.arena, ctx, dom);
                    body_ty = Some(self.infer_value(flag, depth + 1, env2, ctx2, body));
                }
                let clo = match body_ty.filter(|bt| {
                    atomic_type(bt)
                        && bt.is_closed()
                        && std::ptr::eq(*bt, dom)
                        && self.ctx.num_loose_bvars(binder_type) == 0
                        && has_deep_bvar_prefix(env)
                }) {
                    Some(_) => Closure::mk_eval(self.empty_env(), binder_type),
                    None => Closure::mk_infer(self.key_env(env, e), ctx, body),
                };
                value::mk_pi(self.arena, dom, clo)
            }
            Pi { binder_type, body, .. } => {
                let l1 = self.infer_sort_of_v(flag, depth, env, ctx, binder_type);
                let dom = self.arg_value(depth, env, binder_type);
                let fresh = self.mk_bvar_hc(depth, dom);
                let env2 = self.env_extend(env, fresh);
                let ctx2 = value::ctx_extend(self.arena, ctx, dom);
                let l2 = self.infer_sort_of_v(flag, depth + 1, env2, ctx2, body);
                let im = self.ctx.imax(l1, l2);
                let im = self.ctx.simplify(im);
                value::mk_sort(self.arena, im)
            }
            Let { data: &crate::expr::LetData { binder_type, val, body, .. }, .. } => {
                let dom = self.arg_value(depth, env, binder_type);
                if flag == Check {
                    self.infer_sort_of_v(flag, depth, env, ctx, binder_type);
                    let val_ty = self.infer_value(flag, depth, env, ctx, val);
                    assert!(self.conv_types_at(depth, dom, val_ty), "let def_eq failed");
                }
                let slot = self.arg_value(depth, env, val);
                let env2 = self.env_extend(env, slot);
                let ctx2 = value::ctx_extend(self.arena, ctx, dom);
                self.infer_value(flag, depth, env2, ctx2, body)
            }
            Proj { ty_name, idx, structure, .. } => self.infer_proj_v(flag, depth, env, ctx, ty_name, idx, structure),
            _ => unreachable!(),
        };
"""
new = """        let r = match self.ctx.read_expr(e) {
            App { .. } => self.infer_app_v(flag, depth, env, ctx, e),
            Lambda { binder_type, body, .. } =>
                self.qckn_infer_lambda_kind(flag, depth, env, ctx, e, binder_type, body),
            Pi { binder_type, body, .. } =>
                self.qckn_infer_pi_kind(flag, depth, env, ctx, binder_type, body),
            Let { data: &crate::expr::LetData { binder_type, val, body, .. }, .. } =>
                self.qckn_infer_let_kind(flag, depth, env, ctx, binder_type, val, body),
            Proj { ty_name, idx, structure, .. } => self.infer_proj_v(flag, depth, env, ctx, ty_name, idx, structure),
            _ => unreachable!(),
        };
"""
if c.count(old) != 1:
    raise SystemExit(f"match anchor mismatch: {c.count(old)}")
c=c.replace(old,new,1)

anchor = """    fn infer_app_v(&mut self, flag: InferFlag, depth: u32, env: E<'t>, ctx: C<'t>, e: ExprPtr<'t>) -> V<'t> {
"""
helpers = """    #[inline(never)]
    fn qckn_infer_lambda_kind(
        &mut self,
        flag: InferFlag,
        depth: u32,
        env: E<'t>,
        ctx: C<'t>,
        e: ExprPtr<'t>,
        binder_type: ExprPtr<'t>,
        body: ExprPtr<'t>,
    ) -> V<'t> {
        let dom = self.arg_value(depth, env, binder_type);
        let mut body_ty = None;
        if flag == Check {
            self.infer_sort_of_v(flag, depth, env, ctx, binder_type);
            let fresh = self.mk_bvar_hc(depth, dom);
            let env2 = self.env_extend(env, fresh);
            let ctx2 = value::ctx_extend(self.arena, ctx, dom);
            body_ty = Some(self.infer_value(flag, depth + 1, env2, ctx2, body));
        }
        let clo = match body_ty.filter(|bt| {
            atomic_type(bt)
                && bt.is_closed()
                && std::ptr::eq(*bt, dom)
                && self.ctx.num_loose_bvars(binder_type) == 0
                && has_deep_bvar_prefix(env)
        }) {
            Some(_) => Closure::mk_eval(self.empty_env(), binder_type),
            None => Closure::mk_infer(self.key_env(env, e), ctx, body),
        };
        value::mk_pi(self.arena, dom, clo)
    }

    #[inline(never)]
    fn qckn_infer_pi_kind(
        &mut self,
        flag: InferFlag,
        depth: u32,
        env: E<'t>,
        ctx: C<'t>,
        binder_type: ExprPtr<'t>,
        body: ExprPtr<'t>,
    ) -> V<'t> {
        let l1 = self.infer_sort_of_v(flag, depth, env, ctx, binder_type);
        let dom = self.arg_value(depth, env, binder_type);
        let fresh = self.mk_bvar_hc(depth, dom);
        let env2 = self.env_extend(env, fresh);
        let ctx2 = value::ctx_extend(self.arena, ctx, dom);
        let l2 = self.infer_sort_of_v(flag, depth + 1, env2, ctx2, body);
        let im = self.ctx.imax(l1, l2);
        let im = self.ctx.simplify(im);
        value::mk_sort(self.arena, im)
    }

    #[inline(never)]
    fn qckn_infer_let_kind(
        &mut self,
        flag: InferFlag,
        depth: u32,
        env: E<'t>,
        ctx: C<'t>,
        binder_type: ExprPtr<'t>,
        val: ExprPtr<'t>,
        body: ExprPtr<'t>,
    ) -> V<'t> {
        let dom = self.arg_value(depth, env, binder_type);
        if flag == Check {
            self.infer_sort_of_v(flag, depth, env, ctx, binder_type);
            let val_ty = self.infer_value(flag, depth, env, ctx, val);
            assert!(self.conv_types_at(depth, dom, val_ty), "let def_eq failed");
        }
        let slot = self.arg_value(depth, env, val);
        let env2 = self.env_extend(env, slot);
        let ctx2 = value::ctx_extend(self.arena, ctx, dom);
        self.infer_value(flag, depth, env2, ctx2, body)
    }

    #[inline(never)]
    fn infer_app_v(&mut self, flag: InferFlag, depth: u32, env: E<'t>, ctx: C<'t>, e: ExprPtr<'t>) -> V<'t> {
"""
if c.count(anchor) != 1:
    raise SystemExit(f"app anchor mismatch: {c.count(anchor)}")
c=c.replace(anchor,helpers,1)

c=c.replace(
"""    fn infer_proj_v(
""",
"""    #[inline(never)]
    fn infer_proj_v(
""",
1)

p.write_text(c)
print("QCKN_INFER_KIND_ATLAS_PATCH=PASS")
