#!/usr/bin/env python3
from pathlib import Path

p=Path("src/tc.rs")
c=p.read_text()

# Add atomics/imports near the top.
anchor="use InferFlag::*;\n"
insert="""use InferFlag::*;

use std::sync::atomic::{AtomicU64, Ordering as AtomicOrdering};

static QCKN_THM_TOTAL: AtomicU64 = AtomicU64::new(0);
static QCKN_THM_ROOT_VAR: AtomicU64 = AtomicU64::new(0);
static QCKN_THM_ROOT_SORT: AtomicU64 = AtomicU64::new(0);
static QCKN_THM_ROOT_CONST: AtomicU64 = AtomicU64::new(0);
static QCKN_THM_ROOT_APP: AtomicU64 = AtomicU64::new(0);
static QCKN_THM_ROOT_LAM: AtomicU64 = AtomicU64::new(0);
static QCKN_THM_ROOT_PI: AtomicU64 = AtomicU64::new(0);
static QCKN_THM_ROOT_LET: AtomicU64 = AtomicU64::new(0);
static QCKN_THM_ROOT_PROJ: AtomicU64 = AtomicU64::new(0);
static QCKN_THM_ROOT_NAT: AtomicU64 = AtomicU64::new(0);
static QCKN_THM_ROOT_STR: AtomicU64 = AtomicU64::new(0);
static QCKN_THM_LAM_PREFIX_SUM: AtomicU64 = AtomicU64::new(0);
static QCKN_THM_LAM_PREFIX_GE1: AtomicU64 = AtomicU64::new(0);
static QCKN_THM_LAM_PREFIX_GE2: AtomicU64 = AtomicU64::new(0);
static QCKN_THM_LAM_PREFIX_GE4: AtomicU64 = AtomicU64::new(0);
static QCKN_THM_LAM_PREFIX_GE8: AtomicU64 = AtomicU64::new(0);
static QCKN_THM_EXPECTED_PI_AT_ROOT: AtomicU64 = AtomicU64::new(0);
"""
if c.count(anchor)!=1: raise SystemExit("import anchor mismatch")
c=c.replace(anchor,insert,1)

# Add helper/report before impl ExportFile.
anchor2="impl<'p> ExportFile<'p> {\n"
helper=r'''
fn qckn_note_theorem_shape<'a>(d: &Declar<'a>) {
    if std::env::var_os("QCKN_THEOREM_SHAPES").is_none() {
        return;
    }
    let Declar::Theorem { val, info } = d else { return };
    QCKN_THM_TOTAL.fetch_add(1, AtomicOrdering::Relaxed);
    match val.as_ref() {
        crate::expr::Expr::Var { .. } => { QCKN_THM_ROOT_VAR.fetch_add(1, AtomicOrdering::Relaxed); }
        crate::expr::Expr::Sort { .. } => { QCKN_THM_ROOT_SORT.fetch_add(1, AtomicOrdering::Relaxed); }
        crate::expr::Expr::Const { .. } => { QCKN_THM_ROOT_CONST.fetch_add(1, AtomicOrdering::Relaxed); }
        crate::expr::Expr::App { .. } => { QCKN_THM_ROOT_APP.fetch_add(1, AtomicOrdering::Relaxed); }
        crate::expr::Expr::Lambda { .. } => { QCKN_THM_ROOT_LAM.fetch_add(1, AtomicOrdering::Relaxed); }
        crate::expr::Expr::Pi { .. } => { QCKN_THM_ROOT_PI.fetch_add(1, AtomicOrdering::Relaxed); }
        crate::expr::Expr::Let { .. } => { QCKN_THM_ROOT_LET.fetch_add(1, AtomicOrdering::Relaxed); }
        crate::expr::Expr::Proj { .. } => { QCKN_THM_ROOT_PROJ.fetch_add(1, AtomicOrdering::Relaxed); }
        crate::expr::Expr::NatLit { .. } => { QCKN_THM_ROOT_NAT.fetch_add(1, AtomicOrdering::Relaxed); }
        crate::expr::Expr::StringLit { .. } => { QCKN_THM_ROOT_STR.fetch_add(1, AtomicOrdering::Relaxed); }
    }
    let mut depth=0u64;
    let mut cur=*val;
    while let crate::expr::Expr::Lambda { body, .. } = cur.as_ref() {
        depth += 1;
        cur = *body;
    }
    QCKN_THM_LAM_PREFIX_SUM.fetch_add(depth, AtomicOrdering::Relaxed);
    if depth >= 1 { QCKN_THM_LAM_PREFIX_GE1.fetch_add(1, AtomicOrdering::Relaxed); }
    if depth >= 2 { QCKN_THM_LAM_PREFIX_GE2.fetch_add(1, AtomicOrdering::Relaxed); }
    if depth >= 4 { QCKN_THM_LAM_PREFIX_GE4.fetch_add(1, AtomicOrdering::Relaxed); }
    if depth >= 8 { QCKN_THM_LAM_PREFIX_GE8.fetch_add(1, AtomicOrdering::Relaxed); }
    if matches!(info.ty.as_ref(), crate::expr::Expr::Pi { .. }) {
        QCKN_THM_EXPECTED_PI_AT_ROOT.fetch_add(1, AtomicOrdering::Relaxed);
    }
}

fn qckn_report_theorem_shapes() {
    if std::env::var_os("QCKN_THEOREM_SHAPES").is_none() {
        return;
    }
    macro_rules! l { ($x:expr) => { $x.load(AtomicOrdering::Relaxed) } }
    eprintln!(
        "QCKN_THEOREM_SHAPES total={} root_var={} root_sort={} root_const={} root_app={} root_lam={} root_pi={} root_let={} root_proj={} root_nat={} root_str={} lam_prefix_sum={} lam_ge1={} lam_ge2={} lam_ge4={} lam_ge8={} expected_pi_root={}",
        l!(QCKN_THM_TOTAL), l!(QCKN_THM_ROOT_VAR), l!(QCKN_THM_ROOT_SORT),
        l!(QCKN_THM_ROOT_CONST), l!(QCKN_THM_ROOT_APP), l!(QCKN_THM_ROOT_LAM),
        l!(QCKN_THM_ROOT_PI), l!(QCKN_THM_ROOT_LET), l!(QCKN_THM_ROOT_PROJ),
        l!(QCKN_THM_ROOT_NAT), l!(QCKN_THM_ROOT_STR), l!(QCKN_THM_LAM_PREFIX_SUM),
        l!(QCKN_THM_LAM_PREFIX_GE1), l!(QCKN_THM_LAM_PREFIX_GE2), l!(QCKN_THM_LAM_PREFIX_GE4),
        l!(QCKN_THM_LAM_PREFIX_GE8), l!(QCKN_THM_EXPECTED_PI_AT_ROOT),
    );
}

'''
if c.count(anchor2)!=1: raise SystemExit("impl anchor mismatch")
c=c.replace(anchor2,helper+anchor2,1)

# Note shape per theorem.
old="""                    let (_, d) = self.declars.get_index(i).expect("declaration index out of range");
                    i += 1;
                    self.check_declar_with(tctx, cache, sbump.get(), d);
"""
new="""                    let (_, d) = self.declars.get_index(i).expect("declaration index out of range");
                    i += 1;
                    qckn_note_theorem_shape(d);
                    self.check_declar_with(tctx, cache, sbump.get(), d);
"""
if c.count(old)!=1: raise SystemExit("loop anchor mismatch")
c=c.replace(old,new,1)

# Report after all threads/serial complete.
old2="""    pub fn check_all_declars(&self) {
        if self.config.num_threads > 1 {
            self.check_all_declars_par(self.config.num_threads)
        } else {
            self.check_all_declars_serial()
        }
    }
"""
new2="""    pub fn check_all_declars(&self) {
        if self.config.num_threads > 1 {
            self.check_all_declars_par(self.config.num_threads)
        } else {
            self.check_all_declars_serial()
        }
        qckn_report_theorem_shapes();
    }
"""
if c.count(old2)!=1: raise SystemExit("report anchor mismatch")
c=c.replace(old2,new2,1)

p.write_text(c)
print("QCKN_THEOREM_SHAPE_PATCH=PASS")
