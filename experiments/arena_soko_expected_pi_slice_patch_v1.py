#!/usr/bin/env python3
"""Source-pinned conservative expected-Pi/lambda checking vertical slice.

Only exact syntactic root Lambda against an exact syntactic declared Pi is
eligible. No new proof rule or global equality relation is added: the domain
must check as a type and be definitionally equal, the body is inferred with
the existing Check authority under a fresh typed binder, then the dependent
codomain is instantiated and definitionally checked. Everything else uses
the complete unchanged original inference/conversion path.

MG_PI_CHECK_SHADOW=1 independently requires the original bottom-up check
after each successful new judgment, for differential development only.
"""
from pathlib import Path
import sys

src = Path(sys.argv[1])
inf = src/"src/checker/infer.rs"
lib = src/"src/lib.rs"
main = src/"src/main.rs"
s = inf.read_text()
marker = "use InferFlag::{Check, InferOnly};"
assert s.count(marker)==1, "Pinned infer source changed"
s=s.replace(marker,marker+"""
use std::sync::atomic::{AtomicU64,Ordering};
static GOAL_PI_APPLIED: AtomicU64 = AtomicU64::new(0);
pub(crate) fn goal_pi_applied() -> u64 {
    GOAL_PI_APPLIED.load(Ordering::Relaxed)
}
""")
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
        if let (
            Lambda { binder_type, body: term_body, .. },
            Pi { .. }
        ) = (*val.as_ref(), *d.info().ty.as_ref())
        {
            // The existing evaluator of a syntactic Pi provides the
            // certified expected Pi value; never guess a Pi by shape.
            let declared = self.eval(0, empty_env, d.info().ty);
            if let Value::Pi {
                domain: expected_domain,
                body: expected_body,
                ..
            } = declared {
                // Source binder formation and domain conversion.
                self.infer_sort_of_v(Check, 0, empty_env, empty_ctx, binder_type);
                let source_domain = self.arg_value(0, empty_env, binder_type);
                ensure!(
                    self.def_eq_at(0, source_domain, *expected_domain),
                    "goal Pi binder domain not definitionally equal"
                );
                // Open both dependent bodies with the *same* certified
                // bound variable. Preserve original lexical source scope.
                let fresh = self.mk_bvar_hc(0, source_domain);
                let body_env = self.env_extend(empty_env, fresh);
                let body_ctx = value::ctx_extend(self.arena, empty_ctx, source_domain);
                let inferred_body = self.infer_value(Check, 1, body_env, body_ctx, term_body);
                let expected_body_ty =
                    self.apply_closure(1, expected_body, fresh, Some(*expected_domain));
                ensure!(
                    self.def_eq_at(1, inferred_body, expected_body_ty),
                    "goal Pi dependent body not definitionally equal"
                );
                // An opt-in development oracle runs the entire existing
                // complete checker for each accepted candidate judgment.
                if std::env::var_os("MG_PI_CHECK_SHADOW").is_some() {
                    let original = self.infer_value(Check, 0, empty_env, empty_ctx, val);
                    ensure!(
                        self.def_eq_at(0, original, declared),
                        "goal Pi shadow disagrees with original full check"
                    );
                }
                GOAL_PI_APPLIED.fetch_add(1, Ordering::Relaxed);
                return;
            }
        }
        let val_ty = self.infer_value(Check, 0, empty_env, empty_ctx, val);
        let declared = self.eval(0, empty_env, d.info().ty);
        ensure!(self.def_eq_at(0, val_ty, declared), "def_eq failed");
"""
assert s.count(old)==1, "Pinned whole-declaration checking boundary changed"
s=s.replace(old,new)
inf.write_text(s)

l=lib.read_text()
anchor="pub use outcome::{CheckError, Decline, Rejection};"
assert l.count(anchor)==1
l=l.replace(anchor,anchor+"""
/// Development-only explicit expected-Pi use count; never an acceptance warrant.
pub fn goal_pi_applied() -> u64 {
    checker::infer::goal_pi_applied()
}
""")
lib.write_text(l)

m=main.read_text()
anchor="    match export_file.check_all_declars() {\n"
new="""    let checked = export_file.check_all_declars();
    if std::env::var_os("MG_PI_REPORT").is_some() {
        eprintln!("MG_PI_GOAL_APPLIED={}", sokonanoda::goal_pi_applied());
    }
    match checked {
"""
assert m.count(anchor)==1
m=m.replace(anchor,new)
main.write_text(m)
print("EXPECTED_PI_LAMBDA_SLICE=EXACT_SYNTAX_AND_DEPENDENT_TYPED_CHECK_WITH_SHADOW",flush=True)
