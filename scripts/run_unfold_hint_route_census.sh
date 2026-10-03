#!/usr/bin/env bash
set -euo pipefail
V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
ROOT=$(pwd)
rm -rf /tmp/mg-hint-census /tmp/arena-hint

git worktree add /tmp/mg-hint-census "$V2"
cd /tmp/mg-hint-census
python3 - <<'PY'
from pathlib import Path
p=Path('src/conv.rs')
s=p.read_text()
anchor='use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};'
insert=r'''
use std::sync::atomic::{AtomicU64, Ordering};
static HR_UNEQUAL: AtomicU64 = AtomicU64::new(0);
static HR_LH_LT: AtomicU64 = AtomicU64::new(0);
static HR_RH_LT: AtomicU64 = AtomicU64::new(0);
static HR_FIRST_PROGRESS: AtomicU64 = AtomicU64::new(0);
static HR_FIRST_STUCK: AtomicU64 = AtomicU64::new(0);
static HR_SECOND_PROGRESS_AFTER_FIRST_STUCK: AtomicU64 = AtomicU64::new(0);
static HR_SECOND_STUCK: AtomicU64 = AtomicU64::new(0);
static HR_DEMAND_PROGRESS: AtomicU64 = AtomicU64::new(0);
static HR_DEMAND_STUCK: AtomicU64 = AtomicU64::new(0);
static HR_FIRST_CTOR: AtomicU64 = AtomicU64::new(0);
static HR_FIRST_RECURSOR: AtomicU64 = AtomicU64::new(0);
static HR_FIRST_LAM: AtomicU64 = AtomicU64::new(0);
static HR_FIRST_PI: AtomicU64 = AtomicU64::new(0);
static HR_FIRST_UNFOLD: AtomicU64 = AtomicU64::new(0);
fn hr_classify(v: &Value<'_>) {
    match v {
        Value::Rigid { head: RigidHead::Ctor(..), .. } => { HR_FIRST_CTOR.fetch_add(1, Ordering::Relaxed); }
        Value::Rigid { head: RigidHead::Recursor(..)|RigidHead::QuotConst(..), .. } => { HR_FIRST_RECURSOR.fetch_add(1, Ordering::Relaxed); }
        Value::Lam { .. } => { HR_FIRST_LAM.fetch_add(1, Ordering::Relaxed); }
        Value::Pi { .. } => { HR_FIRST_PI.fetch_add(1, Ordering::Relaxed); }
        Value::Unfold { .. } => { HR_FIRST_UNFOLD.fetch_add(1, Ordering::Relaxed); }
        _ => {}
    }
}
pub fn dump_hint_route_census() {
    macro_rules! q { ($n:literal,$x:ident) => { eprintln!(concat!("MG_HINT ",$n,"={}"), $x.load(Ordering::Relaxed)); }; }
    q!("unequal",HR_UNEQUAL); q!("lh_lt",HR_LH_LT); q!("rh_lt",HR_RH_LT);
    q!("first_progress",HR_FIRST_PROGRESS); q!("first_stuck",HR_FIRST_STUCK);
    q!("second_progress_after_first_stuck",HR_SECOND_PROGRESS_AFTER_FIRST_STUCK); q!("second_stuck",HR_SECOND_STUCK);
    q!("demand_progress",HR_DEMAND_PROGRESS); q!("demand_stuck",HR_DEMAND_STUCK);
    q!("first_ctor",HR_FIRST_CTOR); q!("first_recursor",HR_FIRST_RECURSOR); q!("first_lam",HR_FIRST_LAM);
    q!("first_pi",HR_FIRST_PI); q!("first_unfold",HR_FIRST_UNFOLD);
}
'''
if anchor not in s: raise SystemExit('import anchor missing')
s=s.replace(anchor, anchor+insert, 1)
old=r'''                    if lh.is_lt(&rh) {
                        let v2 = self.unfold_value(depth, t2);
                        if !std::ptr::eq(v2, t2) {
                            return self.unify::<true>(depth, t, v2);
                        }
                        let v1 = self.unfold_value(depth, t);
                        if !std::ptr::eq(v1, t) {
                            return self.unify::<true>(depth, v1, t2);
                        }
                        let f2 = self.unfold_value_demand(depth, t2);
                        if std::ptr::eq(f2, t2) {
                            return false;
                        }
                        self.unify::<true>(depth, t, f2)
                    } else if rh.is_lt(&lh) {
                        let v1 = self.unfold_value(depth, t);
                        if !std::ptr::eq(v1, t) {
                            return self.unify::<true>(depth, v1, t2);
                        }
                        let v2 = self.unfold_value(depth, t2);
                        if !std::ptr::eq(v2, t2) {
                            return self.unify::<true>(depth, t, v2);
                        }
                        let f1 = self.unfold_value_demand(depth, t);
                        if std::ptr::eq(f1, t) {
                            return false;
                        }
                        self.unify::<true>(depth, f1, t2)
                    } else {'''
new=r'''                    if lh.is_lt(&rh) {
                        HR_UNEQUAL.fetch_add(1, Ordering::Relaxed); HR_LH_LT.fetch_add(1, Ordering::Relaxed);
                        let v2 = self.unfold_value(depth, t2);
                        if !std::ptr::eq(v2, t2) {
                            HR_FIRST_PROGRESS.fetch_add(1, Ordering::Relaxed); hr_classify(v2);
                            return self.unify::<true>(depth, t, v2);
                        }
                        HR_FIRST_STUCK.fetch_add(1, Ordering::Relaxed);
                        let v1 = self.unfold_value(depth, t);
                        if !std::ptr::eq(v1, t) {
                            HR_SECOND_PROGRESS_AFTER_FIRST_STUCK.fetch_add(1, Ordering::Relaxed);
                            return self.unify::<true>(depth, v1, t2);
                        }
                        HR_SECOND_STUCK.fetch_add(1, Ordering::Relaxed);
                        let f2 = self.unfold_value_demand(depth, t2);
                        if std::ptr::eq(f2, t2) { HR_DEMAND_STUCK.fetch_add(1, Ordering::Relaxed); return false; }
                        HR_DEMAND_PROGRESS.fetch_add(1, Ordering::Relaxed);
                        self.unify::<true>(depth, t, f2)
                    } else if rh.is_lt(&lh) {
                        HR_UNEQUAL.fetch_add(1, Ordering::Relaxed); HR_RH_LT.fetch_add(1, Ordering::Relaxed);
                        let v1 = self.unfold_value(depth, t);
                        if !std::ptr::eq(v1, t) {
                            HR_FIRST_PROGRESS.fetch_add(1, Ordering::Relaxed); hr_classify(v1);
                            return self.unify::<true>(depth, v1, t2);
                        }
                        HR_FIRST_STUCK.fetch_add(1, Ordering::Relaxed);
                        let v2 = self.unfold_value(depth, t2);
                        if !std::ptr::eq(v2, t2) {
                            HR_SECOND_PROGRESS_AFTER_FIRST_STUCK.fetch_add(1, Ordering::Relaxed);
                            return self.unify::<true>(depth, t, v2);
                        }
                        HR_SECOND_STUCK.fetch_add(1, Ordering::Relaxed);
                        let f1 = self.unfold_value_demand(depth, t);
                        if std::ptr::eq(f1, t) { HR_DEMAND_STUCK.fetch_add(1, Ordering::Relaxed); return false; }
                        HR_DEMAND_PROGRESS.fetch_add(1, Ordering::Relaxed);
                        self.unify::<true>(depth, f1, t2)
                    } else {'''
if old not in s: raise SystemExit('routing anchor missing')
s=s.replace(old,new,1)
p.write_text(s)
m=Path('src/main.rs'); x=m.read_text(); x=x.replace('    match out {','    sokonanoda::conv::dump_hint_route_census();\n    match out {',1); m.write_text(x)
PY
cargo test --release --locked
RUSTFLAGS='-C target-cpu=x86-64' cargo build --release --locked
cp target/release/sokonanoda /tmp/mg-hint-census-bin

cd /tmp
git clone --depth 1 https://github.com/leanprover/lean-kernel-arena arena-hint
cd arena-hint
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
/tmp/mg-hint-census-bin /tmp/mg-config.json < _build/tests/init-prelude.ndjson >/dev/null 2>/tmp/preflight.err
/usr/bin/time -f 'WALL_SECONDS=%e' /tmp/mg-hint-census-bin /tmp/mg-config.json < _build/tests/mathlib.ndjson >/dev/null 2>/tmp/hint.stderr
{
 grep -E 'MG_HINT|WALL_SECONDS' /tmp/hint.stderr
} | tee "$ROOT/unfold-hint-route-census.txt"
grep -q 'MG_HINT unequal=' "$ROOT/unfold-hint-route-census.txt"
