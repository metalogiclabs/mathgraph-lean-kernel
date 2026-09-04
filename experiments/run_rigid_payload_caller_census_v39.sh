#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v39-base /tmp/v39-census /tmp/v39-arena

git worktree add /tmp/v39-base "$BASE"
git worktree add /tmp/v39-census "$BASE"

for d in /tmp/v39-base /tmp/v39-census; do
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
p=Path('/tmp/v39-census/src/eval.rs')
s=p.read_text()
s=s.replace('use std::cell::OnceCell;','use std::cell::{OnceCell, RefCell};\nuse std::collections::HashMap;\nuse std::sync::atomic::{AtomicU64, Ordering::Relaxed};',1)
anchor='const FAIL_DEPTH: u8 = 7;\n\n'
insert=r'''const V39_SAMPLE_MASK: u64 = 4095;
static V39_NOCACHE: AtomicU64 = AtomicU64::new(0);
static V39_SAMPLED: AtomicU64 = AtomicU64::new(0);
static V39_RIGID_DIFF_ENV: AtomicU64 = AtomicU64::new(0);
static V39_RIGID_SAME_DIGEST: AtomicU64 = AtomicU64::new(0);
static V39_RIGID_CLOSED: AtomicU64 = AtomicU64::new(0);
static V39_RIGID_HAS_PROJ: AtomicU64 = AtomicU64::new(0);
static V39_HEAD: [AtomicU64; 6] = [const { AtomicU64::new(0) }; 6];
static V39_HEAD_SAME_DIGEST: [AtomicU64; 6] = [const { AtomicU64::new(0) }; 6];
static V39_SPINE: [AtomicU64; 6] = [const { AtomicU64::new(0) }; 6];
static V39_SPINE_SAME_DIGEST: [AtomicU64; 6] = [const { AtomicU64::new(0) }; 6];
thread_local! { static V39_SEEN: RefCell<HashMap<usize, (usize, u8, u64)>> = RefCell::new(HashMap::with_capacity(1 << 15)); }
#[inline] fn v39_head_class(h: value::RigidHead<'_>) -> usize { match h { value::RigidHead::BVar(..)=>0, value::RigidHead::Axiom(..)=>1, value::RigidHead::Ctor(..)=>2, value::RigidHead::Recursor(..)=>3, value::RigidHead::QuotConst(..)=>4, value::RigidHead::Inductive(..)=>5 } }
#[inline] fn v39_spine_bucket(n:u32)->usize { match n {0=>0,1=>1,2=>2,3=>3,4=>4,_=>5} }
#[inline] fn v39_record<'t>(e:ExprPtr<'t>, env:E<'t>, v:V<'t>) {
 let n=V39_NOCACHE.fetch_add(1,Relaxed)+1; if n & V39_SAMPLE_MASK !=0{return;} V39_SAMPLED.fetch_add(1,Relaxed); if e.is_local(){return;}
 let ek=e.as_ref() as *const Expr<'t> as usize; let ep=env as *const value::Env<'t> as usize;
 let (head,spine)=match v {Value::Rigid{head,spine,..}=>(*head,*spine),_=>return}; let dg=v.digest(); let hc=v39_head_class(head); let sb=v39_spine_bucket(spine.len());
 V39_SEEN.with(|cell|{let mut m=cell.borrow_mut(); if let Some(&(old_env,old_h,old_d))=m.get(&ek){if old_env!=ep{V39_RIGID_DIFF_ENV.fetch_add(1,Relaxed);V39_HEAD[hc].fetch_add(1,Relaxed);V39_SPINE[sb].fetch_add(1,Relaxed);if v.is_closed(){V39_RIGID_CLOSED.fetch_add(1,Relaxed);}if spine.has_proj(){V39_RIGID_HAS_PROJ.fetch_add(1,Relaxed);}if old_h==hc as u8&&old_d==dg{V39_RIGID_SAME_DIGEST.fetch_add(1,Relaxed);V39_HEAD_SAME_DIGEST[hc].fetch_add(1,Relaxed);V39_SPINE_SAME_DIGEST[sb].fetch_add(1,Relaxed);}}}m.insert(ek,(ep,hc as u8,dg));});
}
pub(crate) fn v39_report(){let n=V39_NOCACHE.load(Relaxed);let s=V39_SAMPLED.load(Relaxed);let d=V39_RIGID_DIFF_ENV.load(Relaxed);let g=V39_RIGID_SAME_DIGEST.load(Relaxed);let c=V39_RIGID_CLOSED.load(Relaxed);let p=V39_RIGID_HAS_PROJ.load(Relaxed);eprintln!("V39_RIGID nocache={} sampled={} diff_env={} same_digest={} closed={} has_proj={}",n,s,d,g,c,p);if s!=0{eprintln!("V39_RIGID_EXPOSURE_PCT_OF_SAMPLED={:.4}%",100.0*d as f64/s as f64);}if d!=0{eprintln!("V39_RIGID_SAME_DIGEST_PCT={:.4}%",100.0*g as f64/d as f64);eprintln!("V39_RIGID_CLOSED_PCT={:.4}%",100.0*c as f64/d as f64);eprintln!("V39_RIGID_PROJ_PCT={:.4}%",100.0*p as f64/d as f64);}let hn=["bvar","axiom","ctor","recursor","quot","inductive"];for i in 0..6{eprintln!("V39_HEAD name={} diff={} same_digest={}",hn[i],V39_HEAD[i].load(Relaxed),V39_HEAD_SAME_DIGEST[i].load(Relaxed));}let sn=["0","1","2","3","4","5p"];for i in 0..6{eprintln!("V39_SPINE len={} diff={} same_digest={}",sn[i],V39_SPINE[i].load(Relaxed),V39_SPINE_SAME_DIGEST[i].load(Relaxed));}eprintln!("V39_RULE=payload/digest census only; no semantic reuse without exact structural verifier-safe equality");}
'''
assert s.count(anchor)==1;s=s.replace(anchor,anchor+insert,1)
old="""    fn eval_no_cache(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        let first = *self.ctx.read_expr_ref(e);"""
new="""    fn eval_no_cache(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        let v = self.eval_no_cache_inner(depth, env, e);
        v39_record(e, env, v);
        v
    }

    fn eval_no_cache_inner(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        let first = *self.ctx.read_expr_ref(e);"""
assert s.count(old)==1;s=s.replace(old,new,1);p.write_text(s)
p=Path('/tmp/v39-census/src/tc.rs');s=p.read_text();old="""    pub fn check_all_declars(&self) {
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
        crate::eval::v39_report();
    }""";assert s.count(old)==1;p.write_text(s.replace(old,new,1))
PY

cat >/tmp/v39-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
for d in /tmp/v39-base /tmp/v39-census; do (cd "$d" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked); done
cp /tmp/v39-base/target/release/sokonanoda /tmp/v39-base-bin; cp /tmp/v39-census/target/release/sokonanoda /tmp/v39-census-bin
git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v39-arena
cd /tmp/v39-arena; nix develop -c ./lka.py build-test mathlib
/tmp/v39-base-bin /tmp/v39-config.json < _build/tests/mathlib.ndjson >/tmp/v39-base.out 2>/tmp/v39-base.err
/tmp/v39-census-bin /tmp/v39-config.json < _build/tests/mathlib.ndjson >/tmp/v39-census.out 2>/tmp/v39-census.err
cmp /tmp/v39-base.out /tmp/v39-census.out; echo V39_MATHLIB_SEMANTIC_REPLAY=EXACT
grep '^V39_' /tmp/v39-census.err | tee /tmp/v39-census.txt
python3 - <<'PY' | tee /tmp/v39-decision.txt
import re
s=open('/tmp/v39-census.txt').read();heads=[(n,int(d),int(g)) for n,d,g in re.findall(r'V39_HEAD name=(\w+) diff=(\d+) same_digest=(\d+)',s)];sp=[(n,int(d),int(g)) for n,d,g in re.findall(r'V39_SPINE len=(\w+) diff=(\d+) same_digest=(\d+)',s)];assert len(heads)==6 and len(sp)==6
wh=max(heads,key=lambda x:x[1]);wg=max(heads,key=lambda x:x[2]);ws=max(sp,key=lambda x:x[1]);m=re.search(r'V39_RIGID nocache=\d+ sampled=\d+ diff_env=(\d+) same_digest=(\d+)',s);assert m;d=int(m.group(1));g=int(m.group(2));share=100.0*wh[1]/d if d else 0;repeat=100.0*g/d if d else 0
print(f'V39_DOMINANT_HEAD={wh[0]} diff={wh[1]}');print(f'V39_DOMINANT_REPEAT_HEAD={wg[0]} same_digest={wg[2]}');print(f'V39_DOMINANT_SPINE={ws[0]} diff={ws[1]}');print(f'V39_DOMINANT_HEAD_SHARE={share:.4f}%');print(f'V39_RIGID_REPEAT_DIGEST={repeat:.4f}%')
if share>=40: print('DECISION=V39_CONCENTRATED_RIGID_FAMILY__BUILD_EXACT_STRUCTURAL_INTERFACE_FOR_DOMINANT_HEAD')
elif share>=20: print('DECISION=V39_MATERIAL_RIGID_FAMILY__DECOMPOSE_DOMINANT_HEAD_BY_SPINE_PAYLOAD_AND_ORIGIN')
else: print('DECISION=V39_RIGID_TOO_FRAGMENTED__RETURN_TO_CROSS_CLASS_DEPENDENCY_INTERFACE')
PY
