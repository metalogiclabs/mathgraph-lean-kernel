#!/usr/bin/env bash
set -euo pipefail
V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
ROOT=$(pwd)
rm -rf /tmp/mg-cont-census /tmp/arena-cont

git worktree add /tmp/mg-cont-census "$V2"
cd /tmp/mg-cont-census
python3 - <<'PY'
from pathlib import Path
p=Path('src/conv.rs')
s=p.read_text()
anchor='use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};'
insert=r'''
use std::cell::Cell;
use std::sync::atomic::{AtomicU64, Ordering};
thread_local! {
    static UC_CUR: Cell<u32> = const { Cell::new(0) };
    static UC_MAX: Cell<u32> = const { Cell::new(0) };
}
static UC_UNEQUAL: AtomicU64 = AtomicU64::new(0);
static UC_LH_LT: AtomicU64 = AtomicU64::new(0);
static UC_RH_LT: AtomicU64 = AtomicU64::new(0);
static UC_FIRST_UNFOLD: AtomicU64 = AtomicU64::new(0);
static UC_FIRST_CTOR: AtomicU64 = AtomicU64::new(0);
static UC_FIRST_RECURSOR: AtomicU64 = AtomicU64::new(0);
static UC_FIRST_LAM: AtomicU64 = AtomicU64::new(0);
static UC_FIRST_PI: AtomicU64 = AtomicU64::new(0);
static UC_CHAIN_ROOTS: AtomicU64 = AtomicU64::new(0);
static UC_CHAIN_TRUE: AtomicU64 = AtomicU64::new(0);
static UC_CHAIN_FALSE: AtomicU64 = AtomicU64::new(0);
static UC_D1: AtomicU64 = AtomicU64::new(0);
static UC_D2: AtomicU64 = AtomicU64::new(0);
static UC_D3: AtomicU64 = AtomicU64::new(0);
static UC_D4: AtomicU64 = AtomicU64::new(0);
static UC_D5_8: AtomicU64 = AtomicU64::new(0);
static UC_D9_16: AtomicU64 = AtomicU64::new(0);
static UC_D17P: AtomicU64 = AtomicU64::new(0);
static UC_DEPTH_SUM: AtomicU64 = AtomicU64::new(0);
static UC_DEPTH_MAX: AtomicU64 = AtomicU64::new(0);

fn uc_classify(v: &Value<'_>) {
    match v {
        Value::Unfold { .. } => { UC_FIRST_UNFOLD.fetch_add(1, Ordering::Relaxed); }
        Value::Rigid { head: RigidHead::Ctor(..), .. } => { UC_FIRST_CTOR.fetch_add(1, Ordering::Relaxed); }
        Value::Rigid { head: RigidHead::Recursor(..)|RigidHead::QuotConst(..), .. } => { UC_FIRST_RECURSOR.fetch_add(1, Ordering::Relaxed); }
        Value::Lam { .. } => { UC_FIRST_LAM.fetch_add(1, Ordering::Relaxed); }
        Value::Pi { .. } => { UC_FIRST_PI.fetch_add(1, Ordering::Relaxed); }
        _ => {}
    }
}
fn uc_enter() -> bool {
    UC_CUR.with(|c| {
        let old = c.get();
        let new = old + 1;
        c.set(new);
        UC_MAX.with(|m| if new > m.get() { m.set(new); });
        old == 0
    })
}
fn uc_leave(root: bool, result: bool) {
    UC_CUR.with(|c| c.set(c.get() - 1));
    if root {
        let d = UC_MAX.with(|m| { let d=m.get(); m.set(0); d });
        UC_CHAIN_ROOTS.fetch_add(1, Ordering::Relaxed);
        if result { UC_CHAIN_TRUE.fetch_add(1, Ordering::Relaxed); } else { UC_CHAIN_FALSE.fetch_add(1, Ordering::Relaxed); }
        UC_DEPTH_SUM.fetch_add(d as u64, Ordering::Relaxed);
        UC_DEPTH_MAX.fetch_max(d as u64, Ordering::Relaxed);
        match d {
            1 => { UC_D1.fetch_add(1, Ordering::Relaxed); }
            2 => { UC_D2.fetch_add(1, Ordering::Relaxed); }
            3 => { UC_D3.fetch_add(1, Ordering::Relaxed); }
            4 => { UC_D4.fetch_add(1, Ordering::Relaxed); }
            5..=8 => { UC_D5_8.fetch_add(1, Ordering::Relaxed); }
            9..=16 => { UC_D9_16.fetch_add(1, Ordering::Relaxed); }
            _ => { UC_D17P.fetch_add(1, Ordering::Relaxed); }
        }
    }
}
pub fn dump_unfold_continuation_census() {
    macro_rules! q { ($n:literal,$x:ident) => { eprintln!(concat!("MG_CONT ",$n,"={}"), $x.load(Ordering::Relaxed)); }; }
    q!("unequal",UC_UNEQUAL); q!("lh_lt",UC_LH_LT); q!("rh_lt",UC_RH_LT);
    q!("first_unfold",UC_FIRST_UNFOLD); q!("first_ctor",UC_FIRST_CTOR); q!("first_recursor",UC_FIRST_RECURSOR); q!("first_lam",UC_FIRST_LAM); q!("first_pi",UC_FIRST_PI);
    q!("chain_roots",UC_CHAIN_ROOTS); q!("chain_true",UC_CHAIN_TRUE); q!("chain_false",UC_CHAIN_FALSE);
    q!("depth_1",UC_D1); q!("depth_2",UC_D2); q!("depth_3",UC_D3); q!("depth_4",UC_D4); q!("depth_5_8",UC_D5_8); q!("depth_9_16",UC_D9_16); q!("depth_17p",UC_D17P);
    q!("depth_sum",UC_DEPTH_SUM); q!("depth_max",UC_DEPTH_MAX);
}
'''
if anchor not in s: raise SystemExit('import anchor missing')
s=s.replace(anchor, anchor+insert, 1)
old1=r'''                    if lh.is_lt(&rh) {
                        let v2 = self.unfold_value(depth, t2);
                        if !std::ptr::eq(v2, t2) {
                            return self.unify::<true>(depth, t, v2);
                        }'''
new1=r'''                    if lh.is_lt(&rh) {
                        UC_UNEQUAL.fetch_add(1, Ordering::Relaxed); UC_LH_LT.fetch_add(1, Ordering::Relaxed);
                        let v2 = self.unfold_value(depth, t2);
                        if !std::ptr::eq(v2, t2) {
                            uc_classify(v2);
                            let root = uc_enter();
                            let r = self.unify::<true>(depth, t, v2);
                            uc_leave(root, r);
                            return r;
                        }'''
old2=r'''                    } else if rh.is_lt(&lh) {
                        let v1 = self.unfold_value(depth, t);
                        if !std::ptr::eq(v1, t) {
                            return self.unify::<true>(depth, v1, t2);
                        }'''
new2=r'''                    } else if rh.is_lt(&lh) {
                        UC_UNEQUAL.fetch_add(1, Ordering::Relaxed); UC_RH_LT.fetch_add(1, Ordering::Relaxed);
                        let v1 = self.unfold_value(depth, t);
                        if !std::ptr::eq(v1, t) {
                            uc_classify(v1);
                            let root = uc_enter();
                            let r = self.unify::<true>(depth, v1, t2);
                            uc_leave(root, r);
                            return r;
                        }'''
if old1 not in s: raise SystemExit('lh branch anchor missing')
if old2 not in s: raise SystemExit('rh branch anchor missing')
s=s.replace(old1,new1,1).replace(old2,new2,1)
p.write_text(s)
m=Path('src/main.rs'); x=m.read_text(); x=x.replace('    match out {','    sokonanoda::conv::dump_unfold_continuation_census();\n    match out {',1); m.write_text(x)
PY
cargo test --release --locked
RUSTFLAGS='-C target-cpu=x86-64' cargo build --release --locked
cp target/release/sokonanoda /tmp/mg-cont-census-bin

cd /tmp
git clone --depth 1 https://github.com/leanprover/lean-kernel-arena arena-cont
cd arena-cont
nix develop -c ./lka.py build-test init-prelude
nix develop -c ./lka.py build-test mathlib
cat >/tmp/mg-config.json <<EOF
{
  "use_stdin": true,
  "nat_extension": true,
  "string_extension": true,
  "unpermitted_axiom_hard_error": false,
  "unsafe_permit_all_axioms": true,
  "num_threads": 4
}
EOF
/tmp/mg-cont-census-bin /tmp/mg-config.json < _build/tests/init-prelude.ndjson >/dev/null 2>/tmp/preflight.err
/usr/bin/time -f 'WALL_SECONDS=%e' /tmp/mg-cont-census-bin /tmp/mg-config.json < _build/tests/mathlib.ndjson >/dev/null 2>/tmp/cont.stderr
{
  grep -E 'MG_CONT|WALL_SECONDS' /tmp/cont.stderr
} | tee "$ROOT/unfold-continuation-depth-census.txt"
grep -q 'MG_CONT chain_roots=' "$ROOT/unfold-continuation-depth-census.txt"
