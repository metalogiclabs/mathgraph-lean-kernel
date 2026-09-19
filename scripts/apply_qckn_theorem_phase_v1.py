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
new="""    #[inline(never)]
    fn qckn_theorem_statement_phase(&mut self, d: &Declar<'t>) {
        self.check_declar_info_v(d);
    }

    #[inline(never)]
    fn qckn_theorem_proof_infer_phase(&mut self, env: E<'t>, ctx: C<'t>, val: ExprPtr<'t>) -> V<'t> {
        self.infer_value(Check, 0, env, ctx, val)
    }

    #[inline(never)]
    fn qckn_theorem_declared_eval_phase(&mut self, env: E<'t>, d: &Declar<'t>) -> V<'t> {
        self.eval(0, env, d.info().ty)
    }

    #[inline(never)]
    fn qckn_theorem_final_defeq_phase(&mut self, val_ty: V<'t>, declared: V<'t>) {
        assert!(self.def_eq_at(0, val_ty, declared), "def_eq failed");
    }

    pub(crate) fn check_def_like_v(&mut self, d: &Declar<'t>, val: ExprPtr<'t>) {
        let empty_env = self.empty_env();
        let empty_ctx = self.empty_ctx();
        if matches!(d, Declar::Theorem { .. }) {
            self.qckn_theorem_statement_phase(d);
            let val_ty = self.qckn_theorem_proof_infer_phase(empty_env, empty_ctx, val);
            let declared = self.qckn_theorem_declared_eval_phase(empty_env, d);
            self.qckn_theorem_final_defeq_phase(val_ty, declared);
            return;
        }
        self.check_declar_info_v(d);
        let val_ty = self.infer_value(Check, 0, empty_env, empty_ctx, val);
        let declared = self.eval(0, empty_env, d.info().ty);
        assert!(self.def_eq_at(0, val_ty, declared), "def_eq failed");
    }
"""
if c.count(old)!=1:
    raise SystemExit(f"phase anchor count={c.count(old)}")
p.write_text(c.replace(old,new,1))
print("QCKN_THEOREM_PHASE_PATCH=PASS")
