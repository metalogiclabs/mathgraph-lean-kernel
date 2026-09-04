#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v40-base /tmp/v40-census /tmp/v40-arena

git worktree add /tmp/v40-base "$BASE"
git worktree add /tmp/v40-census "$BASE"

for d in /tmp/v40-base /tmp/v40-census; do
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

python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v40-census/src/eval.rs')
s=p.read_text()
s=s.replace('use std::cell::OnceCell;','use std::cell::{OnceCell, RefCell};\nuse std::collections::HashMap;\nuse std::sync::atomic::{AtomicU64, Ordering::Relaxed};',1)
anchor='const FAIL_DEPTH: u8 = 7;\n\n'
insert=r'''const V40_SAMPLE_MASK: u64 = 4095;
static V40_NOCACHE: AtomicU64 = AtomicU64::new(0);
static V40_SAMPLED: AtomicU64 = AtomicU64::new(0);
static V40_BVAR_DIFF_ENV: AtomicU64 = AtomicU64::new(0);
static V40_EMPTY_SPINE: AtomicU64 = AtomicU64::new(0);
static V40_SAME_LEVEL: AtomicU64 = AtomicU64::new(0);
static V40_SAME_TY_PTR: AtomicU64 = AtomicU64::new(0);
static V40_SAME_TY_DIGEST: AtomicU64 = AtomicU64::new(0);
static V40_SAME_TY_CLASS: AtomicU64 = AtomicU64::new(0);
static V40_SAME_LEVEL_TY_DIGEST: AtomicU64 = AtomicU64::new(0);
thread_local! { static V40_SEEN: RefCell<HashMap<usize, (usize,u32,usize,u64,u8)>> = RefCell::new(HashMap::with_capacity(1 << 15)); }
#[inline] fn v40_class(v:V<'_>)->u8 { match v {Value::Rigid{..}=>0,Value::Unfold{..}=>1,Value::Lam{..}=>2,Value::Pi{..}=>3,Value::Sort{..}=>4,Value::NatLit{..}=>5,Value::StrLit{..}=>6,Value::Thunk{..}=>7} }
#[inline] fn v40_record<'t>(e:ExprPtr<'t>, env:E<'t>, v:V<'t>) {
 let n=V40_NOCACHE.fetch_add(1,Relaxed)+1; if n & V40_SAMPLE_MASK != 0{return;} V40_SAMPLED.fetch_add(1,Relaxed); if e.is_local(){return;}
 let (lvl,ty,spine)=match v {Value::Rigid{head:RigidHead::BVar(l,t),spine,..}=>(*l,*t,*spine),_=>return};
 let ek=e.as_ref() as *const Expr<'t> as usize; let ep=env as *const value::Env<'t> as usize; let tp=ty as *const Value<'t> as usize; let td=ty.digest(); let tc=v40_class(ty);
 V40_SEEN.with(|cell|{let mut m=cell.borrow_mut(); if let Some(&(old_env,old_lvl,old_tp,old_td,old_tc))=m.get(&ek){if old_env!=ep{V40_BVAR_DIFF_ENV.fetch_add(1,Relaxed); if spine.len()==0{V40_EMPTY_SPINE.fetch_add(1,Relaxed);} if old_lvl==lvl{V40_SAME_LEVEL.fetch_add(1,Relaxed);} if old_tp==tp{V40_SAME_TY_PTR.fetch_add(1,Relaxed);} if old_td==td{V40_SAME_TY_DIGEST.fetch_add(1,Relaxed);} if old_tc==tc{V40_SAME_TY_CLASS.fetch_add(1,Relaxed);} if old_lvl==lvl&&old_td==td{V40_SAME_LEVEL_TY_DIGEST.fetch_add(1,Relaxed);}}} m.insert(ek,(ep,lvl,tp,td,tc));});
}
pub(crate) fn v40_report(){let n=V40_NOCACHE.load(Relaxed);let s=V40_SAMPLED.load(Relaxed);let d=V40_BVAR_DIFF_ENV.load(Relaxed);let e=V40_EMPTY_SPINE.load(Relaxed);let l=V40_SAME_LEVEL.load(Relaxed);let p=V40_SAME_TY_PTR.load(Relaxed);let g=V40_SAME_TY_DIGEST.load(Relaxed);let c=V40_SAME_TY_CLASS.load(Relaxed);let lg=V40_SAME_LEVEL_TY_DIGEST.load(Relaxed);eprintln!("V40_BVAR nocache={} sampled={} diff_env={} empty_spine={} same_level={} same_ty_ptr={} same_ty_digest={} same_ty_class={} same_level_ty_digest={}",n,s,d,e,l,p,g,c,lg);if d!=0{for (k,v) in [("EMPTY_SPINE",e),("SAME_LEVEL",l),("SAME_TY_PTR",p),("SAME_TY_DIGEST",g),("SAME_TY_CLASS",c),("SAME_LEVEL_TY_DIGEST",lg)]{eprintln!("V40_{}_PCT={:.4}%",k,100.0*v as f64/d as f64);}}eprintln!("V40_RULE=digest/class are census separators only; no reuse without exact verifier-safe equality");}
'''
assert s.count(anchor)==1;s=s.replace(anchor,anchor+insert,1)
old="""    fn eval_no_cache(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        let first = *self.ctx.read_expr_ref(e);"""
new="""    fn eval_no_cache(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        let v = self.eval_no_cache_inner(depth, env, e);
        v40_record(e, env, v);
        v
    }

    fn eval_no_cache_inner(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        let first = *self.ctx.read_expr_ref(e);"""
assert s.count(old)==1;s=s.replace(old,new,1);p.write_text(s)
p=Path('/tmp/v40-census/src/tc.rs');s=p.read_text();old="""    pub fn check_all_declars(&self) {
        if self.config.num_threads > 1 {
            self.check_all_declars_par(self.config.num_threads)
        } else {
            self.check_all_declars_serial()
        }
    }""";new="""    pub fn check_all_declars(&self) {
        if self.config.num_threads > 1 {
            self.check_all_declars_par(self.config.num_threads)
        } else {
            self.check_all_declars_serial()
        }
        crate::eval::v40_report();
    }""";assert s.count(old)==1;p.write_text(s.replace(old,new,1))
PY

cat >/tmp/v40-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
for d in /tmp/v40-base /tmp/v40-census; do (cd "$d" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked); done
cp /tmp/v40-base/target/release/sokonanoda /tmp/v40-base-bin
cp /tmp/v40-census/target/release/sokonanoda /tmp/v40-census-bin
git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v40-arena
cd /tmp/v40-arena
nix develop -c ./lka.py build-test mathlib
/tmp/v40-base-bin /tmp/v40-config.json < _build/tests/mathlib.ndjson >/tmp/v40-base.out 2>/tmp/v40-base.err
/tmp/v40-census-bin /tmp/v40-config.json < _build/tests/mathlib.ndjson >/tmp/v40-census.out 2>/tmp/v40-census.err
cmp /tmp/v40-base.out /tmp/v40-census.out
echo V40_MATHLIB_SEMANTIC_REPLAY=EXACT
grep '^V40_' /tmp/v40-census.err | tee /tmp/v40-census.txt
python3 - <<'PY' | tee /tmp/v40-decision.txt
import re
s=open('/tmp/v40-census.txt').read()
m=re.search(r'V40_BVAR .*diff_env=(\d+).*same_level=(\d+).*same_ty_ptr=(\d+).*same_ty_digest=(\d+).*same_ty_class=(\d+).*same_level_ty_digest=(\d+)',s);assert m
d,l,p,g,c,lg=map(int,m.groups())
for name,v in [('same_level',l),('same_ty_ptr',p),('same_ty_digest',g),('same_ty_class',c),('same_level_ty_digest',lg)]: print(f'V40_{name.upper()}={100.0*v/d if d else 0:.4f}%')
share=100.0*lg/d if d else 0
if share>=40: print('DECISION=V40_SEMANTIC_TYPE_INTERFACE_CONCENTRATED__BUILD_EXACT_TYPE_CANONICALIZATION_PROTOTYPE')
elif share>=15: print('DECISION=V40_MATERIAL_TYPE_INTERFACE__DECOMPOSE_TYPE_CLASS_AND_ORIGIN')
else: print('DECISION=V40_TYPE_DIGEST_TOO_FRAGMENTED__RETURN_TO_BVAR_CREATION_ORIGIN_AND_LIFETIME')
PY
