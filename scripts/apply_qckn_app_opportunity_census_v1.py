#!/usr/bin/env python3
from pathlib import Path

# infer.rs
p=Path("src/infer.rs")
c=p.read_text()

imp="""use std::sync::atomic::{AtomicU64, Ordering::Relaxed};

"""
if imp not in c:
    c=c.replace("use InferFlag::*;\n\n", "use InferFlag::*;\n\n"+imp, 1)

marker="""#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum CheckScope<'a> {
"""
statics="""static APP_ARG_TOTAL: AtomicU64 = AtomicU64::new(0);
static APP_ARG_EXPR_REPEAT: AtomicU64 = AtomicU64::new(0);
static APP_ARG_KEY_REPEAT: AtomicU64 = AtomicU64::new(0);
static APP_ARG_SAME_EXPR_DIFF_ENV: AtomicU64 = AtomicU64::new(0);
static APP_ARG_CACHE_EXACT_CHECKED: AtomicU64 = AtomicU64::new(0);
static APP_ARG_CACHE_EXACT_UNCHECKED: AtomicU64 = AtomicU64::new(0);
static APP_ARG_CACHE_EXACT_OTHER_SCOPE: AtomicU64 = AtomicU64::new(0);
static APP_ARG_CLOSED_SYNTAX: AtomicU64 = AtomicU64::new(0);
static APP_ARG_KIND_APP: AtomicU64 = AtomicU64::new(0);
static APP_ARG_KIND_LAMBDA: AtomicU64 = AtomicU64::new(0);
static APP_ARG_KIND_PI: AtomicU64 = AtomicU64::new(0);
static APP_ARG_KIND_LET: AtomicU64 = AtomicU64::new(0);
static APP_ARG_KIND_PROJ: AtomicU64 = AtomicU64::new(0);
static APP_ARG_KIND_ATOMIC: AtomicU64 = AtomicU64::new(0);
static APP_CONV_TOTAL: AtomicU64 = AtomicU64::new(0);
static APP_CONV_PAIR_REPEAT: AtomicU64 = AtomicU64::new(0);

pub(crate) fn report_app_opportunity_census() {
    if std::env::var_os("QCKN_APP_CENSUS").is_none() {
        return;
    }
    eprintln!(
        "QCKN_APP_CENSUS total={} expr_repeat={} key_repeat={} same_expr_diff_env={} exact_checked={} exact_unchecked={} exact_other_scope={} closed_syntax={} kind_app={} kind_lambda={} kind_pi={} kind_let={} kind_proj={} kind_atomic={} conv_total={} conv_pair_repeat={}",
        APP_ARG_TOTAL.load(Relaxed),
        APP_ARG_EXPR_REPEAT.load(Relaxed),
        APP_ARG_KEY_REPEAT.load(Relaxed),
        APP_ARG_SAME_EXPR_DIFF_ENV.load(Relaxed),
        APP_ARG_CACHE_EXACT_CHECKED.load(Relaxed),
        APP_ARG_CACHE_EXACT_UNCHECKED.load(Relaxed),
        APP_ARG_CACHE_EXACT_OTHER_SCOPE.load(Relaxed),
        APP_ARG_CLOSED_SYNTAX.load(Relaxed),
        APP_ARG_KIND_APP.load(Relaxed),
        APP_ARG_KIND_LAMBDA.load(Relaxed),
        APP_ARG_KIND_PI.load(Relaxed),
        APP_ARG_KIND_LET.load(Relaxed),
        APP_ARG_KIND_PROJ.load(Relaxed),
        APP_ARG_KIND_ATOMIC.load(Relaxed),
        APP_CONV_TOTAL.load(Relaxed),
        APP_CONV_PAIR_REPEAT.load(Relaxed),
    );
}

"""
if statics not in c:
    if marker not in c:
        raise SystemExit("infer marker missing")
    c=c.replace(marker, statics+marker, 1)

old="""            if flag == Check {
                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);
                assert!(self.conv_types_at(depth, domain, arg_ty), "app arg def_eq failed");
            }
"""
new="""            if flag == Check {
                APP_ARG_TOTAL.fetch_add(1, Relaxed);

                if self.ctx.num_loose_bvars(arg) == 0 {
                    APP_ARG_CLOSED_SYNTAX.fetch_add(1, Relaxed);
                }

                let composite = match self.ctx.read_expr(arg) {
                    App { .. } => {
                        APP_ARG_KIND_APP.fetch_add(1, Relaxed);
                        true
                    }
                    Lambda { .. } => {
                        APP_ARG_KIND_LAMBDA.fetch_add(1, Relaxed);
                        true
                    }
                    Pi { .. } => {
                        APP_ARG_KIND_PI.fetch_add(1, Relaxed);
                        true
                    }
                    Let { .. } => {
                        APP_ARG_KIND_LET.fetch_add(1, Relaxed);
                        true
                    }
                    Proj { .. } => {
                        APP_ARG_KIND_PROJ.fetch_add(1, Relaxed);
                        true
                    }
                    _ => {
                        APP_ARG_KIND_ATOMIC.fetch_add(1, Relaxed);
                        false
                    }
                };

                let expr_repeat = !self.tc_cache.census_app_arg_seen_expr.insert(arg);
                if expr_repeat {
                    APP_ARG_EXPR_REPEAT.fetch_add(1, Relaxed);
                }

                if composite {
                    let kenv = self.key_env(env, arg) as *const value::Env<'t> as usize;
                    let key = (kenv, arg);
                    let key_repeat = !self.tc_cache.census_app_arg_seen_key.insert(key);
                    if key_repeat {
                        APP_ARG_KEY_REPEAT.fetch_add(1, Relaxed);
                    } else if expr_repeat {
                        APP_ARG_SAME_EXPR_DIFF_ENV.fetch_add(1, Relaxed);
                    }

                    if let Some(cached) = self.tc_cache.type_cache.get(&key).copied() {
                        let scope = self.uparam_scope();
                        if cached.checked_under == scope {
                            APP_ARG_CACHE_EXACT_CHECKED.fetch_add(1, Relaxed);
                        } else if cached.checked_under == CheckScope::Unchecked {
                            APP_ARG_CACHE_EXACT_UNCHECKED.fetch_add(1, Relaxed);
                        } else {
                            APP_ARG_CACHE_EXACT_OTHER_SCOPE.fetch_add(1, Relaxed);
                        }
                    }
                }

                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);

                APP_CONV_TOTAL.fetch_add(1, Relaxed);
                let da = domain as *const Value<'t> as usize;
                let aa = arg_ty as *const Value<'t> as usize;
                let pair = if da < aa { (da, aa) } else { (aa, da) };
                if !self.tc_cache.census_app_conv_seen.insert(pair) {
                    APP_CONV_PAIR_REPEAT.fetch_add(1, Relaxed);
                }

                assert!(self.conv_types_at(depth, domain, arg_ty), "app arg def_eq failed");
            }
"""
if c.count(old) != 1:
    raise SystemExit(f"infer_app anchor mismatch: {c.count(old)}")
c=c.replace(old,new,1)
p.write_text(c)

# util.rs
p=Path("src/util.rs")
c=p.read_text()

field="""    pub(crate) type_cache: FxHashMap<(usize, ExprPtr<'t>), crate::infer::CachedType<'a>>,
"""
field_new=field+"""    pub(crate) census_app_arg_seen_expr: FxHashSet<ExprPtr<'t>>,
    pub(crate) census_app_arg_seen_key: FxHashSet<(usize, ExprPtr<'t>)>,
    pub(crate) census_app_conv_seen: FxHashSet<(usize, usize)>,
"""
if c.count(field) != 1:
    raise SystemExit("util field anchor mismatch")
c=c.replace(field,field_new,1)

init="""            type_cache: session_fx_hash_map(),
"""
init_new=init+"""            census_app_arg_seen_expr: session_small_fx_hash_set(),
            census_app_arg_seen_key: session_small_fx_hash_set(),
            census_app_conv_seen: session_small_fx_hash_set(),
"""
if c.count(init) != 1:
    raise SystemExit("util init anchor mismatch")
c=c.replace(init,init_new,1)

clear="""        self.type_cache.clear();
"""
clear_new=clear+"""        self.census_app_arg_seen_expr.clear();
        self.census_app_arg_seen_key.clear();
        self.census_app_conv_seen.clear();
"""
if c.count(clear) != 1:
    raise SystemExit("util clear anchor mismatch")
c=c.replace(clear,clear_new,1)

clear_s="""        shrink_map(&mut self.type_cache);
"""
clear_s_new=clear_s+"""        shrink_set(&mut self.census_app_arg_seen_expr);
        shrink_set(&mut self.census_app_arg_seen_key);
        shrink_set(&mut self.census_app_conv_seen);
"""
if c.count(clear_s) != 1:
    raise SystemExit("util clear_session anchor mismatch")
c=c.replace(clear_s,clear_s_new,1)
p.write_text(c)

# tc.rs
p=Path("src/tc.rs")
c=p.read_text()
old="""        std::thread::scope(|sco| {
            std::thread::Builder::new()
                .stack_size(crate::STACK_SIZE)
                .spawn_scoped(sco, || self.run_session((0, total), || None))
                .unwrap()
                .join()
                .expect("serial checker thread panicked");
        });
"""
new=old+"""        crate::infer::report_app_opportunity_census();
"""
if c.count(old) != 1:
    raise SystemExit("tc serial anchor mismatch")
c=c.replace(old,new,1)
p.write_text(c)

print("QCKN_APP_OPPORTUNITY_CENSUS_V1_PATCH=PASS")
