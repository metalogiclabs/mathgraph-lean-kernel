#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v38-base /tmp/v38-census /tmp/v38-arena

git worktree add /tmp/v38-base "$BASE"
git worktree add /tmp/v38-census "$BASE"

# Verified v29 wall-time seed: Pi-only force collapse in both arms.
for d in /tmp/v38-base /tmp/v38-census; do
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

# v38 refines v37: same global expression + different physical environment,
# decomposed by semantic value class and by the existing semantic digest.
# Digest equality is a census separator only; it is NOT treated as a proof-safe cache key.
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v38-census/src/eval.rs')
s=p.read_text()
s=s.replace('use std::cell::OnceCell;','use std::cell::{OnceCell, RefCell};\nuse std::collections::HashMap;\nuse std::sync::atomic::{AtomicU64, Ordering::Relaxed};',1)
anchor='const FAIL_DEPTH: u8 = 7;\n\n'
insert=r'''const V38_SAMPLE_MASK: u64 = 4095;
static V38_NOCACHE: AtomicU64 = AtomicU64::new(0);
static V38_SAMPLED: AtomicU64 = AtomicU64::new(0);
static V38_DIFF_ENV: AtomicU64 = AtomicU64::new(0);
static V38_SAME_CLASS: AtomicU64 = AtomicU64::new(0);
static V38_SAME_DIGEST: AtomicU64 = AtomicU64::new(0);
static V38_SAME_DIGEST_CLOSED: AtomicU64 = AtomicU64::new(0);
static V38_LOCAL_EXPR_SKIPPED: AtomicU64 = AtomicU64::new(0);
static V38_CLEARS: AtomicU64 = AtomicU64::new(0);
static V38_DIFF_BY_CLASS: [AtomicU64; 8] = [const { AtomicU64::new(0) }; 8];
static V38_SAME_CLASS_BY_CLASS: [AtomicU64; 8] = [const { AtomicU64::new(0) }; 8];
static V38_SAME_DIGEST_BY_CLASS: [AtomicU64; 8] = [const { AtomicU64::new(0) }; 8];

thread_local! {
    static V38_SEEN: RefCell<HashMap<usize, (usize, u8, u64)>> = RefCell::new(HashMap::with_capacity(1 << 15));
}

#[inline]
fn v38_value_class(v: V<'_>) -> u8 {
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
fn v38_record<'t>(e: ExprPtr<'t>, env: E<'t>, v: V<'t>) {
    let n = V38_NOCACHE.fetch_add(1, Relaxed) + 1;
    if n & V38_SAMPLE_MASK != 0 { return; }
    V38_SAMPLED.fetch_add(1, Relaxed);
    if e.is_local() {
        V38_LOCAL_EXPR_SKIPPED.fetch_add(1, Relaxed);
        return;
    }
    let ek = e.as_ref() as *const Expr<'t> as usize;
    let ep = env as *const value::Env<'t> as usize;
    let vc = v38_value_class(v);
    let dg = v.digest();
    V38_SEEN.with(|cell| {
        let mut m = cell.borrow_mut();
        if m.len() >= (1 << 18) {
            m.clear();
            V38_CLEARS.fetch_add(1, Relaxed);
        }
        if let Some(&(old_env, old_c, old_d)) = m.get(&ek) {
            if old_env != ep {
                V38_DIFF_ENV.fetch_add(1, Relaxed);
                V38_DIFF_BY_CLASS[vc as usize].fetch_add(1, Relaxed);
                if old_c == vc {
                    V38_SAME_CLASS.fetch_add(1, Relaxed);
                    V38_SAME_CLASS_BY_CLASS[vc as usize].fetch_add(1, Relaxed);
                    if old_d == dg {
                        V38_SAME_DIGEST.fetch_add(1, Relaxed);
                        V38_SAME_DIGEST_BY_CLASS[vc as usize].fetch_add(1, Relaxed);
                        if dg & 1 == 1 { V38_SAME_DIGEST_CLOSED.fetch_add(1, Relaxed); }
                    }
                }
            }
        }
        m.insert(ek, (ep, vc, dg));
    });
}

pub(crate) fn v38_report() {
    let n=V38_NOCACHE.load(Relaxed);
    let s=V38_SAMPLED.load(Relaxed);
    let d=V38_DIFF_ENV.load(Relaxed);
    let c=V38_SAME_CLASS.load(Relaxed);
    let g=V38_SAME_DIGEST.load(Relaxed);
    let gc=V38_SAME_DIGEST_CLOSED.load(Relaxed);
    let l=V38_LOCAL_EXPR_SKIPPED.load(Relaxed);
    let z=V38_CLEARS.load(Relaxed);
    eprintln!("V38_INTERFACE nocache={} sampled={} diff_env={} same_class={} same_digest={} same_digest_closed={} local_expr_skipped={} map_clears={}",n,s,d,c,g,gc,l,z);
    if s != 0 { eprintln!("V38_DIFF_ENV_PCT_OF_SAMPLED={:.4}%",100.0*d as f64/s as f64); }
    if d != 0 {
        eprintln!("V38_SAME_CLASS_PCT_OF_DIFF_ENV={:.4}%",100.0*c as f64/d as f64);
        eprintln!("V38_SAME_DIGEST_PCT_OF_DIFF_ENV={:.4}%",100.0*g as f64/d as f64);
    }
    let names=["lam","pi","sort","nat","str","rigid","unfold","thunk"];
    for i in 0..8 {
        let di=V38_DIFF_BY_CLASS[i].load(Relaxed);
        let ci=V38_SAME_CLASS_BY_CLASS[i].load(Relaxed);
        let gi=V38_SAME_DIGEST_BY_CLASS[i].load(Relaxed);
        eprintln!("V38_CLASS name={} diff={} same_class={} same_digest={}",names[i],di,ci,gi);
    }
    eprintln!("V38_RULE=digest equality is a semantic-interface census separator only; any implementation requires an exact structural/verifier-safe comparator");
}

'''
assert s.count(anchor)==1
s=s.replace(anchor,anchor+insert,1)
old="""    fn eval_no_cache(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        let first = *self.ctx.read_expr_ref(e);"""
new="""    fn eval_no_cache(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        let v = self.eval_no_cache_inner(depth, env, e);
        v38_record(e, env, v);
        v
    }

    fn eval_no_cache_inner(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        let first = *self.ctx.read_expr_ref(e);"""
assert s.count(old)==1
s=s.replace(old,new,1)
p.write_text(s)

p=Path('/tmp/v38-census/src/tc.rs')
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
        crate::eval::v38_report();
    }"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY

cat >/tmp/v38-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

for d in /tmp/v38-base /tmp/v38-census; do
  (cd "$d" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
done
cp /tmp/v38-base/target/release/sokonanoda /tmp/v38-base-bin
cp /tmp/v38-census/target/release/sokonanoda /tmp/v38-census-bin

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v38-arena
cd /tmp/v38-arena
nix develop -c ./lka.py build-test mathlib

/tmp/v38-base-bin /tmp/v38-config.json < _build/tests/mathlib.ndjson >/tmp/v38-base.out 2>/tmp/v38-base.err
/tmp/v38-census-bin /tmp/v38-config.json < _build/tests/mathlib.ndjson >/tmp/v38-census.out 2>/tmp/v38-census.err
cmp /tmp/v38-base.out /tmp/v38-census.out
echo V38_MATHLIB_SEMANTIC_REPLAY=EXACT

grep '^V38_' /tmp/v38-census.err | tee /tmp/v38-census.txt
python3 - <<'PY' | tee /tmp/v38-decision.txt
import re
s=open('/tmp/v38-census.txt').read()
def pct(k):
    m=re.search(rf'{k}=([0-9.]+)%',s); assert m,k; return float(m.group(1))
def classes():
    out=[]
    for n,d,c,g in re.findall(r'V38_CLASS name=(\w+) diff=(\d+) same_class=(\d+) same_digest=(\d+)',s):
        out.append((n,int(d),int(c),int(g)))
    return out
q=pct('V38_SAME_DIGEST_PCT_OF_DIFF_ENV')
d=pct('V38_DIFF_ENV_PCT_OF_SAMPLED')
cs=classes(); assert len(cs)==8
winner=max(cs,key=lambda x:x[3])
print(f'V38_SAME_DIGEST_PCT={q:.4f}%')
print(f'V38_DIFF_ENV_EXPOSURE_PCT={d:.4f}%')
print(f'V38_DOMINANT_DIGEST_CLASS={winner[0]} same_digest={winner[3]} diff={winner[1]}')
if q >= 20.0 and d >= 20.0:
    print('DECISION=V38_LARGE_SEMANTIC_INTERFACE_BASIN__BUILD_EXACT_STRUCTURAL_QUOTIENT_FOR_DOMINANT_CLASS')
elif q >= 5.0:
    print('DECISION=V38_MATERIAL_INTERFACE_SIGNAL__DECOMPOSE_DOMINANT_CLASS_PAYLOAD_AND_CALLER')
else:
    print('DECISION=V38_DIGEST_INTERFACE_TOO_SMALL__REFINE_DEPENDENCY_INTERFACE_BEYOND_VALUE_DIGEST')
print('V38_NEXT=never reuse digest equality directly; next implementation gate must use exact verifier-safe structural equality')
PY
