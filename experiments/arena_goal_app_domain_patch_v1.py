#!/usr/bin/env python3
"""Source-pinned, proof-rule-preserving expected-type check for application args.

ONLY a syntactic lambda argument with a verified Pi expected DOMAIN enters
the bidirectional check. Every needed domain formation, definitional equality,
dependent codomain substitution and body typing obligation is checked with
the original Soko kernel. All other applications use exactly the original
inference path. Opt-in MG_APP_DOMAIN_SHADOW re-runs original inference and
conversion after each successful new check.

This is a candidate checker modification, not a soundness theorem.
"""
from pathlib import Path
import sys

root=Path(sys.argv[1])
inf=root/"src/checker/infer.rs"
lib=root/"src/lib.rs"
main=root/"src/main.rs"
s=inf.read_text()

marker="use InferFlag::{Check, InferOnly};"
assert s.count(marker)==1,("upstream import changed",s.count(marker))
s=s.replace(marker,marker+"""
use std::sync::atomic::{AtomicU64, Ordering};
static APP_PI_APPLIED: AtomicU64 = AtomicU64::new(0);
pub(crate) fn goal_app_pi_applied() -> u64 {
    APP_PI_APPLIED.load(Ordering::Relaxed)
}
""")

marker="    fn infer_app_v(\n"
assert s.count(marker)==1
helper="""    /// Check an argument against the already checked/derived function-domain
    /// type. This preserves source binder indices, universe parameters and
    /// the kernel's original definitional-equality authority.
    #[inline]
    fn check_app_against_domain(
        &mut self,
        depth: u32,
        env: E<'t>,
        ctx: C<'t>,
        arg: ExprPtr<'t>,
        expected: V<'t>,
    ) {
        if let Lambda { binder_type, body, .. } = *arg.as_ref() {
            if let Value::Pi {
                domain: expected_domain,
                body: expected_body,
                ..
            } = self.force_all(depth, expected)
            {
                self.infer_sort_of_v(Check, depth, env, ctx, binder_type);
                let source_domain = self.arg_value(depth, env, binder_type);
                ensure!(
                    self.conv_types_at(depth, *expected_domain, source_domain),
                    "app arg def_eq failed"
                );
                let fresh = self.mk_bvar_hc(depth, source_domain);
                let body_env = self.env_extend(env, fresh);
                let body_ctx = value::ctx_extend(self.arena, ctx, source_domain);
                let body_type = self.infer_value(
                    Check, depth + 1, body_env, body_ctx, body
                );
                let expected_body_type = self.apply_closure(
                    depth + 1, expected_body, fresh, Some(*expected_domain)
                );
                ensure!(
                    self.conv_types_at(depth + 1, expected_body_type, body_type),
                    "app arg def_eq failed"
                );
                // Recheck every successful new judgment under the complete
                // source inference+conversion rule in protected shadow mode.
                if std::env::var_os("MG_APP_DOMAIN_SHADOW").is_some() {
                    let old_type=self.infer_value(Check, depth, env, ctx, arg);
                    ensure!(
                        self.conv_types_at(depth, expected, old_type),
                        "app arg shadow disagrees with original kernel"
                    );
                }
                APP_PI_APPLIED.fetch_add(1, Ordering::Relaxed);
                return;
            }
        }
        let inferred = self.infer_value(Check, depth, env, ctx, arg);
        ensure!(
            self.conv_types_at(depth, expected, inferred),
            "app arg def_eq failed"
        );
    }

"""
s=s.replace(marker,helper+marker)

old="""                if flag == Check {
                    let arg_ty = self.infer_value(flag, depth, env, ctx, arg);
                    let domain = self.eval_arg(depth, tenv, binder_type);
                    ensure!(
                        self.conv_types_at(depth, domain, arg_ty),
                        "app arg def_eq failed"
                    );
                }
"""
new="""                if flag == Check {
                    let domain = self.eval_arg(depth, tenv, binder_type);
                    self.check_app_against_domain(depth, env, ctx, arg, domain);
                }
"""
assert s.count(old)==1,("telescope Pi original source changed",s.count(old))
s=s.replace(old,new)

old="""            if flag == Check {
                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);
                ensure!(
                    self.conv_types_at(depth, domain, arg_ty),
                    "app arg def_eq failed"
                );
            }
"""
new="""            if flag == Check {
                self.check_app_against_domain(depth, env, ctx, arg, domain);
            }
"""
assert s.count(old)==2,("normal and long app source changed",s.count(old))
s=s.replace(old,new)
inf.write_text(s)

l=lib.read_text()
mark="pub use outcome::{CheckError, Decline, Rejection};"
assert l.count(mark)==1
l=l.replace(mark,mark+"""
/// Count guarded, successfully checked dependent lambda application arguments.
pub fn goal_app_pi_applied() -> u64 {
    checker::infer::goal_app_pi_applied()
}
""")
lib.write_text(l)

m=main.read_text()
old="    match export_file.check_all_declars() {\n"
new="""    let checked = export_file.check_all_declars();
    if std::env::var_os("MG_APP_DOMAIN_REPORT").is_some() {
        eprintln!("MG_APP_PI_APPLIED={}", sokonanoda::goal_app_pi_applied());
    }
    match checked {
"""
assert m.count(old)==1,"checker output boundary changed"
m=m.replace(old,new)
main.write_text(m)

print("APP_DOMAIN_TYPED_PI=EXACT_DEPENDENT_CHECK_OR_ORIGINAL_FALLBACK",flush=True)
