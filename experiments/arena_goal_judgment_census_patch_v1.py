#!/usr/bin/env python3
"""Source-pinned, diagnostic-only Soko goal-judgment census.

The instrumentation observes the existing trusted checker. It does not
replace, skip, add, or admit any proof judgment. Counts are whole-process
aggregates and are not estimates of saved instructions. Exact cache hits
already represent work the upstream checker avoids.
"""
from pathlib import Path
import sys

src = Path(sys.argv[1])
inf = src / "src/checker/infer.rs"
lib = src / "src/lib.rs"
main = src / "src/main.rs"
s = inf.read_text()
assert s.count("use InferFlag::{Check, InferOnly};") == 1
s = s.replace(
    "use InferFlag::{Check, InferOnly};",
    """use InferFlag::{Check, InferOnly};
use std::sync::atomic::{AtomicU64, Ordering};

static INFER_CALL: AtomicU64 = AtomicU64::new(0);
static INFER_CHECK: AtomicU64 = AtomicU64::new(0);
static INFER_ONLY: AtomicU64 = AtomicU64::new(0);
static INFER_VAR: AtomicU64 = AtomicU64::new(0);
static NONVAR: AtomicU64 = AtomicU64::new(0);
static CACHE_HIT: AtomicU64 = AtomicU64::new(0);
static CACHE_CHECK_HIT: AtomicU64 = AtomicU64::new(0);
static CACHE_INFER_ONLY_HIT: AtomicU64 = AtomicU64::new(0);
static CACHE_SCOPE_INELIGIBLE: AtomicU64 = AtomicU64::new(0);
static CACHE_MISS: AtomicU64 = AtomicU64::new(0);
static REUSED_CLOSED: AtomicU64 = AtomicU64::new(0);
static COLD_APP: AtomicU64 = AtomicU64::new(0);
static COLD_LAMBDA: AtomicU64 = AtomicU64::new(0);
static COLD_PI: AtomicU64 = AtomicU64::new(0);
static COLD_LET: AtomicU64 = AtomicU64::new(0);
static COLD_PROJ: AtomicU64 = AtomicU64::new(0);
static CHECKED_APP_ARGS: AtomicU64 = AtomicU64::new(0);
static ALL_APP_ARGS: AtomicU64 = AtomicU64::new(0);
static DECL_DEF_LIKE: AtomicU64 = AtomicU64::new(0);
static DECL_THEOREM: AtomicU64 = AtomicU64::new(0);
static DECL_LAMBDA: AtomicU64 = AtomicU64::new(0);
static DECL_RAW_PI: AtomicU64 = AtomicU64::new(0);
static DECL_LAMBDA_PI: AtomicU64 = AtomicU64::new(0);

#[inline(always)]
fn census_inc(c: &AtomicU64) {
    c.fetch_add(1, Ordering::Relaxed);
}

pub(crate) fn goal_census_json() -> serde_json::Value {
    let n = |c: &AtomicU64| c.load(Ordering::Relaxed);
    serde_json::json!({
        "authority": "diagnostic-only; does not change proof or conversion rules",
        "infer_calls": n(&INFER_CALL),
        "infer_check_calls": n(&INFER_CHECK),
        "infer_only_calls": n(&INFER_ONLY),
        "infer_var_calls": n(&INFER_VAR),
        "infer_nonvar_calls": n(&NONVAR),
        "type_cache_eligible_hits": n(&CACHE_HIT),
        "type_cache_check_hits": n(&CACHE_CHECK_HIT),
        "type_cache_infer_only_hits": n(&CACHE_INFER_ONLY_HIT),
        "type_cache_existing_ineligible_scope": n(&CACHE_SCOPE_INELIGIBLE),
        "type_cache_true_misses": n(&CACHE_MISS),
        "closed_source_already_reused": n(&REUSED_CLOSED),
        "cold_app": n(&COLD_APP),
        "cold_lambda": n(&COLD_LAMBDA),
        "cold_pi": n(&COLD_PI),
        "cold_let": n(&COLD_LET),
        "cold_proj": n(&COLD_PROJ),
        "app_arg_steps": n(&ALL_APP_ARGS),
        "app_arg_checked": n(&CHECKED_APP_ARGS),
        "def_like_declarations": n(&DECL_DEF_LIKE),
        "theorem_declarations": n(&DECL_THEOREM),
        "root_lambda_declarations": n(&DECL_LAMBDA),
        "raw_pi_declared_types": n(&DECL_RAW_PI),
        "raw_lambda_pi_opportunities": n(&DECL_LAMBDA_PI),
        "note": "Counters observe executions, not unique semantic judgments; raw-Pi is conservative and not proof of eligible dependent transport."
    })
}
"""
)
old=String = """    ) -> V<'t> {
        if let &Var { dbj_idx, .. } = e.as_ref() {
            return ctx.lookup(dbj_idx).expect("loose bvar in infer");
        }
        self.infer_nonvar(flag, depth, env, ctx, e)
    }
"""
new="""    ) -> V<'t> {
        census_inc(&INFER_CALL);
        if flag == Check {
            census_inc(&INFER_CHECK);
        } else {
            census_inc(&INFER_ONLY);
        }
        if let &Var { dbj_idx, .. } = e.as_ref() {
            census_inc(&INFER_VAR);
            return ctx.lookup(dbj_idx).expect("loose bvar in infer");
        }
        self.infer_nonvar(flag, depth, env, ctx, e)
    }
"""
assert s.count(old) == 1, "infer_value source diverged"
s = s.replace(old,new)
needle="""    ) -> V<'t> {
        match *e {
            Var { dbj_idx, .. } => return ctx.lookup(dbj_idx).expect("loose bvar in infer"),"""
replacement="""    ) -> V<'t> {
        census_inc(&NONVAR);
        match *e {
            Var { dbj_idx, .. } => return ctx.lookup(dbj_idx).expect("loose bvar in infer"),"""
assert s.count(needle)==1, "infer_nonvar source diverged"
s=s.replace(needle,replacement)
needle="""        if let Some(cached) = self.tc_cache.type_cache.get(&key)
            && (flag == InferOnly || cached.checked_under == scope)
        {
            return cached.result;
        }
"""
replacement="""        if let Some(cached) = self.tc_cache.type_cache.get(&key) {
            if flag == InferOnly || cached.checked_under == scope {
                census_inc(&CACHE_HIT);
                if flag == Check {
                    census_inc(&CACHE_CHECK_HIT);
                } else {
                    census_inc(&CACHE_INFER_ONLY_HIT);
                }
                return cached.result;
            }
            census_inc(&CACHE_SCOPE_INELIGIBLE);
        } else {
            census_inc(&CACHE_MISS);
        }
"""
assert s.count(needle)==1, "type cache source diverged"
s=s.replace(needle,replacement)
needle="""        let known = reusable.is_some_and(|u| self.ctx.checked_closed.contains(&(e, u)));
        let requested = flag;"""
replacement="""        let known = reusable.is_some_and(|u| self.ctx.checked_closed.contains(&(e, u)));
        if known {
            census_inc(&REUSED_CLOSED);
        }
        let requested = flag;"""
assert s.count(needle)==1
s=s.replace(needle,replacement)
repls=[
("App { .. } => self.infer_app_v(flag, depth, env, ctx, e),", """App { .. } => {
                census_inc(&COLD_APP);
                self.infer_app_v(flag, depth, env, ctx, e)
            },"""),
("""            Lambda {
                binder_type, body, ..
            } => {
                let dom = self.arg_value""","""            Lambda {
                binder_type, body, ..
            } => {
                census_inc(&COLD_LAMBDA);
                let dom = self.arg_value"""),
("""            Pi {
                binder_type, body, ..
            } => {
                let l1 = self.infer_sort_of_v""","""            Pi {
                binder_type, body, ..
            } => {
                census_inc(&COLD_PI);
                let l1 = self.infer_sort_of_v"""),
("""            } => {
                let dom = self.arg_value(depth, env, binder_type);
                if flag == Check {
                    self.infer_sort_of_v""","""            } => {
                census_inc(&COLD_LET);
                let dom = self.arg_value(depth, env, binder_type);
                if flag == Check {
                    self.infer_sort_of_v"""),
("""            } => self.infer_proj_v(flag, depth, env, ctx, ty_name, idx, structure),""","""            } => {
                census_inc(&COLD_PROJ);
                self.infer_proj_v(flag, depth, env, ctx, ty_name, idx, structure)
            },""")
]
for a,b in repls:
    assert s.count(a)==1,("dispatch changed",a[:100],s.count(a))
    s=s.replace(a,b)
needle="""        for &arg in rev_args.iter().rev() {
            if let Some((tenv, t)) = telescope"""
replacement="""        for &arg in rev_args.iter().rev() {
            census_inc(&ALL_APP_ARGS);
            if flag == Check {
                census_inc(&CHECKED_APP_ARGS);
            }
            if let Some((tenv, t)) = telescope"""
assert s.count(needle)==1
s=s.replace(needle,replacement)
needle="""        while let Some(arg) = args.pop() {
            let fty_f = self.force_all(depth, fty);"""
replacement="""        while let Some(arg) = args.pop() {
            census_inc(&ALL_APP_ARGS);
            if flag == Check {
                census_inc(&CHECKED_APP_ARGS);
            }
            let fty_f = self.force_all(depth, fty);"""
assert s.count(needle)==1
s=s.replace(needle,replacement)
needle="""    pub(crate) fn check_def_like_v(&mut self, d: &Declar<'t>, val: ExprPtr<'t>) {
        self.check_declar_info_v(d);
        let empty_env = self.empty_env();"""
replacement="""    pub(crate) fn check_def_like_v(&mut self, d: &Declar<'t>, val: ExprPtr<'t>) {
        census_inc(&DECL_DEF_LIKE);
        if matches!(d, Declar::Theorem { .. }) {
            census_inc(&DECL_THEOREM);
        }
        let is_lambda = matches!(val.as_ref(), Lambda { .. });
        let raw_pi = matches!(d.info().ty.as_ref(), Pi { .. });
        if is_lambda {
            census_inc(&DECL_LAMBDA);
        }
        if raw_pi {
            census_inc(&DECL_RAW_PI);
        }
        if is_lambda && raw_pi {
            census_inc(&DECL_LAMBDA_PI);
        }
        self.check_declar_info_v(d);
        let empty_env = self.empty_env();"""
assert s.count(needle)==1,"top declaration check changed"
s=s.replace(needle,replacement)
inf.write_text(s)

l=lib.read_text()
old="pub use outcome::{CheckError, Decline, Rejection};"
assert l.count(old)==1
l=l.replace(old,old+"\n/// Diagnostic-only source-pinned goal-judgment execution census.\npub fn goal_judgment_census() -> serde_json::Value {\n    checker::infer::goal_census_json()\n}\n")
lib.write_text(l)

m=main.read_text()
old="    match export_file.check_all_declars() {\n"
new="""    // Print only on explicit diagnostic opt-in; the checker result remains
    // the same even for rejected/declined inputs.
    let check_result = export_file.check_all_declars();
    if std::env::var_os("MG_GOAL_CENSUS").is_some() {
        eprintln!("MG_GOAL_CENSUS={}", sokonanoda::goal_judgment_census());
    }
    match check_result {
"""
assert m.count(old)==1,"main boundary changed"
m=m.replace(old,new)
main.write_text(m)
print("GOAL_JUDGMENT_CENSUS_PATCH=DIAGNOSTIC_ONLY_EXACT_CACHE_AND_RAW_GOALS",flush=True)
