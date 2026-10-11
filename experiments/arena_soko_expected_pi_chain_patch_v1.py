#!/usr/bin/env python3
"""Certified dependent expected-Pi checking through a complete lambda spine.

Source-pinned soundness requirements:
- Only a syntactic Lambda checked against an already kernel-evaluated Pi
  can be decomposed into a binder and a dependent codomain obligation.
- Binder annotations remain well-formed via original Check and conversion.
- Each dependent codomain is instantiated by the original typed closure
  operation with the same fresh variable under the original lexical scope.
- The final nonlambda obligation uses original full infer+definitional eq.
- All unsupported expected types fall back to the original inference.
- MG_PI_CHECK_SHADOW reruns complete original root-check on every use.

This is an experimental implementation of a standard type-theoretic rule,
not a source-free equality assumption or a released checker.
"""
from pathlib import Path
import sys
src=Path(sys.argv[1])
inf=src/"src/checker/infer.rs"
lib=src/"src/lib.rs"
main=src/"src/main.rs"
s=inf.read_text()
anchor="use InferFlag::{Check, InferOnly};"
assert s.count(anchor)==1
s=s.replace(anchor,anchor+"""
use std::sync::atomic::{AtomicU64,Ordering};
static GOAL_PI_APPLIED: AtomicU64 = AtomicU64::new(0);
static GOAL_PI_BINDERS: AtomicU64 = AtomicU64::new(0);
pub(crate) fn goal_pi_counts() -> (u64,u64) {
    (GOAL_PI_APPLIED.load(Ordering::Relaxed),
     GOAL_PI_BINDERS.load(Ordering::Relaxed))
}
""")
anchor="    pub(crate) fn check_def_like_v(&mut self, d: &Declar<'t>, val: ExprPtr<'t>) {"
assert s.count(anchor)==1
method="""    /// Exact expected type checking. Every fallback is ordinary Check +
    /// def_eq; each lambda/Π case is only a decomposition of that judgment.
    fn check_goal_pi_chain(
        &mut self,
        depth: u32,
        env: E<'t>,
        ctx: C<'t>,
        term: ExprPtr<'t>,
        expected: V<'t>,
    ) {
        if let Lambda { binder_type, body, .. } = *term.as_ref() {
            // Never infer a Pi from syntactic similarity: force via existing
            // semantically checked conversion evaluator.
            let exposed = self.force_all(depth, expected);
            if let Value::Pi {
                domain: expected_domain,
                body: expected_body,
                ..
            } = exposed
            {
                self.infer_sort_of_v(Check, depth, env, ctx, binder_type);
                let source_domain = self.arg_value(depth, env, binder_type);
                ensure!(
                    self.def_eq_at(depth, source_domain, *expected_domain),
                    "goal-directed binder-domain mismatch"
                );
                let fresh = self.mk_bvar_hc(depth, source_domain);
                let next_env = self.env_extend(env, fresh);
                let next_ctx = value::ctx_extend(self.arena, ctx, source_domain);
                let expected_codomain = self.apply_closure(
                    depth + 1, expected_body, fresh, Some(*expected_domain)
                );
                // Recursive checking *inside* the existing complete checker
                // avoids synthesizing each intermediate Pi closure.
                self.check_goal_pi_chain(
                    depth + 1, next_env, next_ctx, body, expected_codomain
                );
                GOAL_PI_BINDERS.fetch_add(1, Ordering::Relaxed);
                return;
            }
        }
        let inferred = self.infer_value(Check, depth, env, ctx, term);
        ensure!(
            self.def_eq_at(depth, inferred, expected),
            "goal-directed fallback type mismatch"
        );
    }

"""
s=s.replace(anchor,method+anchor)
old="""        self.check_declar_info_v(d);
        let empty_env = self.empty_env();
        let empty_ctx = self.empty_ctx();
        let val_ty = self.infer_value(Check, 0, empty_env, empty_ctx, val);
        let declared = self.eval(0, empty_env, d.info().ty);
        ensure!(self.def_eq_at(0, val_ty, declared), "def_eq failed");
"""
new="""        self.check_declar_info_v(d);
        let empty_env = self.empty_env();
        let empty_ctx = self.empty_ctx();
        if let (Lambda { .. }, Pi { .. }) = (*val.as_ref(), *d.info().ty.as_ref()) {
            let declared = self.eval(0, empty_env, d.info().ty);
            self.check_goal_pi_chain(0, empty_env, empty_ctx, val, declared);
            // Shadow is only used by the experimental qualification harness.
            if std::env::var_os("MG_PI_CHECK_SHADOW").is_some() {
                let original = self.infer_value(Check, 0, empty_env, empty_ctx, val);
                ensure!(
                    self.def_eq_at(0, original, declared),
                    "goal Pi chain shadow disagrees with original full checker"
                );
            }
            GOAL_PI_APPLIED.fetch_add(1, Ordering::Relaxed);
            return;
        }
        let val_ty = self.infer_value(Check, 0, empty_env, empty_ctx, val);
        let declared = self.eval(0, empty_env, d.info().ty);
        ensure!(self.def_eq_at(0, val_ty, declared), "def_eq failed");
"""
assert s.count(old)==1
s=s.replace(old,new)
inf.write_text(s)

l=lib.read_text()
anchor="pub use outcome::{CheckError, Decline, Rejection};"
assert l.count(anchor)==1
l=l.replace(anchor,anchor+"""
/// Diagnostic counts of the experimental goal-directed Pi checking rule.
pub fn goal_pi_counts() -> (u64,u64) {
    checker::infer::goal_pi_counts()
}
""")
lib.write_text(l)

m=main.read_text()
anchor="    match export_file.check_all_declars() {\n"
new="""    let checked = export_file.check_all_declars();
    if std::env::var_os("MG_PI_REPORT").is_some() {
        let (roots, binders) = sokonanoda::goal_pi_counts();
        eprintln!("MG_PI_GOAL_APPLIED={roots}");
        eprintln!("MG_PI_GOAL_BINDERS={binders}");
    }
    match checked {
"""
assert m.count(anchor)==1
m=m.replace(anchor,new)
main.write_text(m)
print("GOAL_DIRECTED_PI_CHAIN=CHECKED_DEPENDENT_BINDERS_AND_ORIGINAL_FALLBACK",flush=True)
