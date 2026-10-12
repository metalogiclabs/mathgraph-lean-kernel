#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v37-base /tmp/v37-census /tmp/v37-arena

git worktree add /tmp/v37-base "$BASE"
git worktree add /tmp/v37-census "$BASE"

# Verified v29 wall-time seed: Pi-only force collapse in both arms.
for d in /tmp/v37-base /tmp/v37-census; do
python3 - "$d" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/eval.rs'
s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {
        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {
        if matches!(v, Value::Pi { .. }) { return v; }
        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY
done

# Census arm only. Sample 1/4096 no-cache evaluations. The strong quotient event is:
# same global expression, different physical environment, exact same semantic value pointer.
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v37-census/src/eval.rs')
s=p.read_text()
s=s.replace('use std::cell::OnceCell;','use std::cell::{OnceCell, RefCell};\nuse std::collections::HashMap;\nuse std::sync::atomic::{AtomicU64, Ordering::Relaxed};',1)
anchor='const FAIL_DEPTH: u8 = 7;\n\n'
insert=r'''const V37_SAMPLE_MASK: u64 = 4095;
static V37_NOCACHE: AtomicU64 = AtomicU64::new(0);
static V37_SAMPLED: AtomicU64 = AtomicU64::new(0);
static V37_DIFF_ENV: AtomicU64 = AtomicU64::new(0);
static V37_SAME_PTR: AtomicU64 = AtomicU64::new(0);
static V37_SAME_CLASS: AtomicU64 = AtomicU64::new(0);
static V37_LOCAL_EXPR_SKIPPED: AtomicU64 = AtomicU64::new(0);
static V37_CLEARS: AtomicU64 = AtomicU64::new(0);

thread_local! {
    static V37_SEEN: RefCell<HashMap<usize, (usize, usize, u8)>> = RefCell::new(HashMap::with_capacity(1 << 15));
}

#[inline]
fn v37_value_class(v: V<'_>) -> u8 {
    match v {
        Value::Lam { .. } => 0,
        Value::Pi { .. } => 1,
        Value::Sort { .. } => 2,
        Value::NatLit { .. } => 3,
        Value::StrLit { .. } => 4,
        Value::Rigid { .. } => 5,
        Value::Unfold { .. } => 6,
        Value::Thunk { .. } => 7,
    }
}

#[inline]
fn v37_record<'t>(e: ExprPtr<'t>, env: E<'t>, v: V<'t>) {
    let n = V37_NOCACHE.fetch_add(1, Relaxed) + 1;
    if n & V37_SAMPLE_MASK != 0 { return; }
    V37_SAMPLED.fetch_add(1, Relaxed);
    if e.is_local() {
        V37_LOCAL_EXPR_SKIPPED.fetch_add(1, Relaxed);
        return;
    }
    let ek = e.as_ref() as *const Expr<'t> as usize;
    let ep = env as *const value::Env<'t> as usize;
    let vp = v as *const Value<'t> as usize;
    let vc = v37_value_class(v);
    V37_SEEN.with(|cell| {
        let mut m = cell.borrow_mut();
        if m.len() >= (1 << 18) {
            m.clear();
            V37_CLEARS.fetch_add(1, Relaxed);
        }
        if let Some(&(old_env, old_v, old_c)) = m.get(&ek) {
            if old_env != ep {
                V37_DIFF_ENV.fetch_add(1, Relaxed);
                if old_v == vp { V37_SAME_PTR.fetch_add(1, Relaxed); }
                if old_c == vc { V37_SAME_CLASS.fetch_add(1, Relaxed); }
            }
        }
        m.insert(ek, (ep, vp, vc));
    });
}

pub(crate) fn v37_report() {
    let n=V37_NOCACHE.load(Relaxed);
    let s=V37_SAMPLED.load(Relaxed);
    let d=V37_DIFF_ENV.load(Relaxed);
    let p=V37_SAME_PTR.load(Relaxed);
    let c=V37_SAME_CLASS.load(Relaxed);
    let l=V37_LOCAL_EXPR_SKIPPED.load(Relaxed);
    let z=V37_CLEARS.load(Relaxed);
    eprintln!("V37_TRAJECTORY_QUOTIENT nocache={} sampled={} diff_env={} exact_same_value={} same_value_class={} local_expr_skipped={} map_clears={}", n,s,d,p,c,l,z);
    if s != 0 {
        eprintln!("V37_DIFF_ENV_PCT_OF_SAMPLED={:.4}%", 100.0*d as f64/s as f64);
    }
    if d != 0 {
        eprintln!("V37_EXACT_QUOTIENT_PCT_OF_DIFF_ENV={:.4}%", 100.0*p as f64/d as f64);
        eprintln!("V37_COARSE_CLASS_PCT_OF_DIFF_ENV={:.4}%", 100.0*c as f64/d as f64);
    }
    eprintln!("V37_RULE=exact_same_value is a conservative lower bound: same global Expr, different Env pointer, identical semantic Value pointer");
}

'''
assert s.count(anchor)==1
s=s.replace(anchor,anchor+insert,1)
old="""    fn eval_no_cache(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        let first = *self.ctx.read_expr_ref(e);"""
new="""    fn eval_no_cache(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        let v = self.eval_no_cache_inner(depth, env, e);
        v37_record(e, env, v);
        v
    }

    fn eval_no_cache_inner(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        let first = *self.ctx.read_expr_ref(e);"""
assert s.count(old)==1
s=s.replace(old,new,1)
p.write_text(s)

p=Path('/tmp/v37-census/src/tc.rs')
s=p.read_text()
old="""    pub fn check_all_declars(&self) {
        if self.config.num_threads > 1 {
            self.check_all_declars_par(self.config.num_threads)
        } else {
            self.check_all_declars_serial()
        }
    }"""
new="""    pub fn check_all_declars(&self) {
        if self.config.num_threads > 1 {
            self.check_all_declars_par(self.config.num_threads)
        } else {
            self.check_all_declars_serial()
        }
        crate::eval::v37_report();
    }"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY

cat >/tmp/v37-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

for d in /tmp/v37-base /tmp/v37-census; do
  (cd "$d" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
done
cp /tmp/v37-base/target/release/sokonanoda /tmp/v37-base-bin
cp /tmp/v37-census/target/release/sokonanoda /tmp/v37-census-bin

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v37-arena
cd /tmp/v37-arena
nix develop -c ./lka.py build-test mathlib

/tmp/v37-base-bin /tmp/v37-config.json < _build/tests/mathlib.ndjson >/tmp/v37-base.out 2>/tmp/v37-base.err
/tmp/v37-census-bin /tmp/v37-config.json < _build/tests/mathlib.ndjson >/tmp/v37-census.out 2>/tmp/v37-census.err
cmp /tmp/v37-base.out /tmp/v37-census.out
echo V37_MATHLIB_SEMANTIC_REPLAY=EXACT

grep '^V37_' /tmp/v37-census.err | tee /tmp/v37-census.txt
python3 - <<'PY' | tee /tmp/v37-decision.txt
import re
s=open('/tmp/v37-census.txt').read()
def grab(k):
    m=re.search(rf'{k}=([0-9.]+)%',s)
    assert m,k
    return float(m.group(1))
q=grab('V37_EXACT_QUOTIENT_PCT_OF_DIFF_ENV')
d=grab('V37_DIFF_ENV_PCT_OF_SAMPLED')
print(f'V37_EXACT_QUOTIENT_PCT={q:.4f}%')
print(f'V37_DIFF_ENV_EXPOSURE_PCT={d:.4f}%')
if q >= 25.0 and d >= 20.0:
    print('DECISION=V37_LARGE_VERIFIED_QUOTIENT_BASIN__ADVANCE_VALUE_DOMAIN_TRAJECTORY_REPRESENTATION')
elif q >= 10.0 and d >= 10.0:
    print('DECISION=V37_MATERIAL_QUOTIENT_BASIN__DECOMPOSE_BY_VALUE_CLASS_AND_CALLER')
else:
    print('DECISION=V37_EXACT_POINTER_QUOTIENT_TOO_SMALL__REFINE_SEMANTIC_INTERFACE_BEFORE_REPRESENTATION_CHANGE')
print('V37_INTERPRETATION=exact pointer equality is a lower bound, not a complete semantic quotient')
PY
