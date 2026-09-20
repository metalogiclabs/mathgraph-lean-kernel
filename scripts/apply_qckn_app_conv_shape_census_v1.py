#!/usr/bin/env python3
from pathlib import Path

# --- util.rs ---
p=Path("src/util.rs")
c=p.read_text()

field="""    pub(crate) type_cache: FxHashMap<(usize, ExprPtr<'t>), crate::infer::CachedType<'a>>,
"""
field_new=field+"""    pub(crate) census_app_conv_seen: FxHashSet<(usize, usize)>,
"""
if c.count(field) != 1:
    raise SystemExit(f"type_cache field anchor mismatch: {c.count(field)}")
c=c.replace(field,field_new,1)

init="""            type_cache: session_fx_hash_map(),
"""
init_new=init+"""            census_app_conv_seen: session_small_fx_hash_set(),
"""
if c.count(init) != 1:
    raise SystemExit(f"type_cache init anchor mismatch: {c.count(init)}")
c=c.replace(init,init_new,1)

clear="""        self.type_cache.clear();
"""
clear_new=clear+"""        self.census_app_conv_seen.clear();
"""
if c.count(clear) != 1:
    raise SystemExit(f"type_cache clear anchor mismatch: {c.count(clear)}")
c=c.replace(clear,clear_new,1)

clear_s="""        shrink_map(&mut self.type_cache);
"""
clear_s_new=clear_s+"""        shrink_set(&mut self.census_app_conv_seen);
"""
if c.count(clear_s) != 1:
    raise SystemExit(f"type_cache clear_session anchor mismatch: {c.count(clear_s)}")
c=c.replace(clear_s,clear_s_new,1)
p.write_text(c)

# --- conv.rs ---
p=Path("src/conv.rs")
c=p.read_text()

imports="""use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};
"""
imports_new=imports+"""use std::sync::atomic::{AtomicU64, Ordering::Relaxed};
"""
if c.count(imports) != 1:
    raise SystemExit("conv import anchor mismatch")
c=c.replace(imports,imports_new,1)

anchor="""fn rigid_head_eq<'a>(hx: RigidHead<'a>, hy: RigidHead<'a>) -> bool {
"""
statics=r"""
static APP_CONV_TOTAL: AtomicU64 = AtomicU64::new(0);
static APP_CONV_REPEAT: AtomicU64 = AtomicU64::new(0);
static APP_CONV_EXISTING_POS_HIT: AtomicU64 = AtomicU64::new(0);

static SH_PTR: AtomicU64 = AtomicU64::new(0);
static SH_PTR_R: AtomicU64 = AtomicU64::new(0);
static SH_RIGID_0: AtomicU64 = AtomicU64::new(0);
static SH_RIGID_0_R: AtomicU64 = AtomicU64::new(0);
static SH_RIGID_12: AtomicU64 = AtomicU64::new(0);
static SH_RIGID_12_R: AtomicU64 = AtomicU64::new(0);
static SH_RIGID_34: AtomicU64 = AtomicU64::new(0);
static SH_RIGID_34_R: AtomicU64 = AtomicU64::new(0);
static SH_RIGID_58: AtomicU64 = AtomicU64::new(0);
static SH_RIGID_58_R: AtomicU64 = AtomicU64::new(0);
static SH_RIGID_916: AtomicU64 = AtomicU64::new(0);
static SH_RIGID_916_R: AtomicU64 = AtomicU64::new(0);
static SH_RIGID_17P: AtomicU64 = AtomicU64::new(0);
static SH_RIGID_17P_R: AtomicU64 = AtomicU64::new(0);
static SH_RIGID_DIFF: AtomicU64 = AtomicU64::new(0);
static SH_RIGID_DIFF_R: AtomicU64 = AtomicU64::new(0);
static SH_UNFOLD_UNFOLD: AtomicU64 = AtomicU64::new(0);
static SH_UNFOLD_UNFOLD_R: AtomicU64 = AtomicU64::new(0);
static SH_UNFOLD_RIGID: AtomicU64 = AtomicU64::new(0);
static SH_UNFOLD_RIGID_R: AtomicU64 = AtomicU64::new(0);
static SH_PI_PI: AtomicU64 = AtomicU64::new(0);
static SH_PI_PI_R: AtomicU64 = AtomicU64::new(0);
static SH_LAM_LAM: AtomicU64 = AtomicU64::new(0);
static SH_LAM_LAM_R: AtomicU64 = AtomicU64::new(0);
static SH_SORT_SORT: AtomicU64 = AtomicU64::new(0);
static SH_SORT_SORT_R: AtomicU64 = AtomicU64::new(0);
static SH_OTHER: AtomicU64 = AtomicU64::new(0);
static SH_OTHER_R: AtomicU64 = AtomicU64::new(0);

fn census_same_rigid_head<'a>(x: RigidHead<'a>, y: RigidHead<'a>) -> bool {
    match (x, y) {
        (RigidHead::BVar(a, _), RigidHead::BVar(b, _)) => a == b,
        (RigidHead::Axiom(nx, lx), RigidHead::Axiom(ny, ly))
        | (RigidHead::Ctor(nx, lx), RigidHead::Ctor(ny, ly))
        | (RigidHead::Recursor(nx, lx), RigidHead::Recursor(ny, ly))
        | (RigidHead::QuotConst(nx, lx), RigidHead::QuotConst(ny, ly))
        | (RigidHead::Inductive(nx, lx), RigidHead::Inductive(ny, ly)) => nx == ny && lx == ly,
        _ => false,
    }
}

fn census_bump(shape: u8, repeated: bool) {
    let (all, rep) = match shape {
        0 => (&SH_PTR, &SH_PTR_R),
        1 => (&SH_RIGID_0, &SH_RIGID_0_R),
        2 => (&SH_RIGID_12, &SH_RIGID_12_R),
        3 => (&SH_RIGID_34, &SH_RIGID_34_R),
        4 => (&SH_RIGID_58, &SH_RIGID_58_R),
        5 => (&SH_RIGID_916, &SH_RIGID_916_R),
        6 => (&SH_RIGID_17P, &SH_RIGID_17P_R),
        7 => (&SH_RIGID_DIFF, &SH_RIGID_DIFF_R),
        8 => (&SH_UNFOLD_UNFOLD, &SH_UNFOLD_UNFOLD_R),
        9 => (&SH_UNFOLD_RIGID, &SH_UNFOLD_RIGID_R),
        10 => (&SH_PI_PI, &SH_PI_PI_R),
        11 => (&SH_LAM_LAM, &SH_LAM_LAM_R),
        12 => (&SH_SORT_SORT, &SH_SORT_SORT_R),
        _ => (&SH_OTHER, &SH_OTHER_R),
    };
    all.fetch_add(1, Relaxed);
    if repeated {
        rep.fetch_add(1, Relaxed);
    }
}

pub(crate) fn report_app_conv_shape_census() {
    if std::env::var_os("QCKN_APP_CONV_SHAPE_CENSUS").is_none() {
        return;
    }
    eprintln!(
        "QCKN_APP_CONV_SHAPE total={} repeat={} existing_pos_hit={} ptr={} ptr_r={} rigid0={} rigid0_r={} rigid12={} rigid12_r={} rigid34={} rigid34_r={} rigid58={} rigid58_r={} rigid916={} rigid916_r={} rigid17p={} rigid17p_r={} rigid_diff={} rigid_diff_r={} unfold_unfold={} unfold_unfold_r={} unfold_rigid={} unfold_rigid_r={} pi_pi={} pi_pi_r={} lam_lam={} lam_lam_r={} sort_sort={} sort_sort_r={} other={} other_r={}",
        APP_CONV_TOTAL.load(Relaxed),
        APP_CONV_REPEAT.load(Relaxed),
        APP_CONV_EXISTING_POS_HIT.load(Relaxed),
        SH_PTR.load(Relaxed), SH_PTR_R.load(Relaxed),
        SH_RIGID_0.load(Relaxed), SH_RIGID_0_R.load(Relaxed),
        SH_RIGID_12.load(Relaxed), SH_RIGID_12_R.load(Relaxed),
        SH_RIGID_34.load(Relaxed), SH_RIGID_34_R.load(Relaxed),
        SH_RIGID_58.load(Relaxed), SH_RIGID_58_R.load(Relaxed),
        SH_RIGID_916.load(Relaxed), SH_RIGID_916_R.load(Relaxed),
        SH_RIGID_17P.load(Relaxed), SH_RIGID_17P_R.load(Relaxed),
        SH_RIGID_DIFF.load(Relaxed), SH_RIGID_DIFF_R.load(Relaxed),
        SH_UNFOLD_UNFOLD.load(Relaxed), SH_UNFOLD_UNFOLD_R.load(Relaxed),
        SH_UNFOLD_RIGID.load(Relaxed), SH_UNFOLD_RIGID_R.load(Relaxed),
        SH_PI_PI.load(Relaxed), SH_PI_PI_R.load(Relaxed),
        SH_LAM_LAM.load(Relaxed), SH_LAM_LAM_R.load(Relaxed),
        SH_SORT_SORT.load(Relaxed), SH_SORT_SORT_R.load(Relaxed),
        SH_OTHER.load(Relaxed), SH_OTHER_R.load(Relaxed),
    );
}

"""
if c.count(anchor) != 1:
    raise SystemExit("conv rigid_head anchor mismatch")
c=c.replace(anchor,statics+anchor,1)

method_anchor="""    pub(crate) fn conv_types_at(&mut self, depth: u32, a: V<'t>, b: V<'t>) -> bool {
        self.unbudgeted(|s| s.unify::<true>(depth, a, b))
    }
"""
method_new=method_anchor+r"""
    pub(crate) fn conv_types_at_app_census(&mut self, depth: u32, a: V<'t>, b: V<'t>) -> bool {
        let a = self.force_thunk(depth, a);
        let b = self.force_thunk(depth, b);
        APP_CONV_TOTAL.fetch_add(1, Relaxed);

        let aa = a as *const Value<'t> as usize;
        let bb = b as *const Value<'t> as usize;
        let pair = if aa < bb { (aa, bb) } else { (bb, aa) };
        let repeated = !self.tc_cache.census_app_conv_seen.insert(pair);
        if repeated {
            APP_CONV_REPEAT.fetch_add(1, Relaxed);
        }

        let shape = if std::ptr::eq(a, b) {
            0
        } else {
            match (a, b) {
                (
                    Value::Rigid { head: hx, spine: sx, .. },
                    Value::Rigid { head: hy, spine: sy, .. },
                ) if census_same_rigid_head(*hx, *hy) => {
                    let k = sx.len().max(sy.len());
                    match k {
                        0 => 1,
                        1..=2 => 2,
                        3..=4 => 3,
                        5..=8 => 4,
                        9..=16 => 5,
                        _ => 6,
                    }
                }
                (Value::Rigid { .. }, Value::Rigid { .. }) => 7,
                (Value::Unfold { .. }, Value::Unfold { .. }) => 8,
                (Value::Unfold { .. }, Value::Rigid { .. })
                | (Value::Rigid { .. }, Value::Unfold { .. }) => 9,
                (Value::Pi { .. }, Value::Pi { .. }) => 10,
                (Value::Lam { .. }, Value::Lam { .. }) => 11,
                (Value::Sort { .. }, Value::Sort { .. }) => 12,
                _ => 13,
            }
        };
        census_bump(shape, repeated);

        if !std::ptr::eq(a, b) && (is_cacheable(a) || is_cacheable(b)) {
            let key = pair;
            if self.tc_cache.conv_cache_pos.contains(&key) {
                APP_CONV_EXISTING_POS_HIT.fetch_add(1, Relaxed);
            }
        }

        if std::ptr::eq(a, b) {
            true
        } else {
            self.unbudgeted(|s| s.unify_general::<true>(depth, a, b))
        }
    }
"""
if c.count(method_anchor) != 1:
    raise SystemExit("conv_types_at anchor mismatch")
c=c.replace(method_anchor,method_new,1)
p.write_text(c)

# --- infer.rs ---
p=Path("src/infer.rs")
c=p.read_text()
old="""                assert!(self.conv_types_at(depth, domain, arg_ty), "app arg def_eq failed");
"""
new="""                assert!(self.conv_types_at_app_census(depth, domain, arg_ty), "app arg def_eq failed");
"""
if c.count(old) != 1:
    raise SystemExit(f"infer app conv anchor mismatch: {c.count(old)}")
c=c.replace(old,new,1)
p.write_text(c)

# --- tc.rs ---
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
new=old+"""        crate::conv::report_app_conv_shape_census();
"""
if c.count(old) != 1:
    raise SystemExit("tc serial anchor mismatch")
c=c.replace(old,new,1)
p.write_text(c)

print("QCKN_APP_CONV_SHAPE_CENSUS_V1_PATCH=PASS")
