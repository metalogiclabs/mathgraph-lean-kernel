#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v41-base /tmp/v41-census /tmp/v41-arena

git worktree add /tmp/v41-base "$BASE"
git worktree add /tmp/v41-census "$BASE"

# Retain the verified Pi-only incumbent in both arms.
for d in /tmp/v41-base /tmp/v41-census; do
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

# Census arm: BVar producer economics + major consumer exposure.
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v41-census/src/eval.rs')
s=p.read_text()
s=s.replace('use std::cell::OnceCell;','use std::cell::OnceCell;\nuse std::sync::atomic::{AtomicU64, Ordering::Relaxed};',1)
anchor='const FAIL_DEPTH: u8 = 7;\n\n'
insert=r'''static V41_MK_CALLS: AtomicU64 = AtomicU64::new(0);
static V41_MK_HITS: AtomicU64 = AtomicU64::new(0);
static V41_MK_NEWS: AtomicU64 = AtomicU64::new(0);
static V41_FORCE_SEEN: AtomicU64 = AtomicU64::new(0);
static V41_APPLY_FUN_SEEN: AtomicU64 = AtomicU64::new(0);
static V41_APPLY_ARG_SEEN: AtomicU64 = AtomicU64::new(0);
static V41_CANON_SEEN: AtomicU64 = AtomicU64::new(0);
static V41_EMPTY_FORCE: AtomicU64 = AtomicU64::new(0);
static V41_EMPTY_APPLY_FUN: AtomicU64 = AtomicU64::new(0);
static V41_EMPTY_APPLY_ARG: AtomicU64 = AtomicU64::new(0);
static V41_EMPTY_CANON: AtomicU64 = AtomicU64::new(0);
#[inline] fn v41_bvar_empty(v: V<'_>) -> bool { matches!(v, Value::Rigid { head: RigidHead::BVar(_, _), spine, .. } if spine.len()==0) }
#[inline] fn v41_consume(v: V<'_>, kind: u8) {
 if !matches!(v, Value::Rigid { head: RigidHead::BVar(_, _), .. }) { return; }
 match kind {
  0 => { V41_FORCE_SEEN.fetch_add(1,Relaxed); if v41_bvar_empty(v){V41_EMPTY_FORCE.fetch_add(1,Relaxed);} }
  1 => { V41_APPLY_FUN_SEEN.fetch_add(1,Relaxed); if v41_bvar_empty(v){V41_EMPTY_APPLY_FUN.fetch_add(1,Relaxed);} }
  2 => { V41_APPLY_ARG_SEEN.fetch_add(1,Relaxed); if v41_bvar_empty(v){V41_EMPTY_APPLY_ARG.fetch_add(1,Relaxed);} }
  3 => { V41_CANON_SEEN.fetch_add(1,Relaxed); if v41_bvar_empty(v){V41_EMPTY_CANON.fetch_add(1,Relaxed);} }
  _ => {}
 }
}
pub(crate) fn v41_report(){
 let calls=V41_MK_CALLS.load(Relaxed); let hits=V41_MK_HITS.load(Relaxed); let news=V41_MK_NEWS.load(Relaxed);
 let f=V41_FORCE_SEEN.load(Relaxed); let af=V41_APPLY_FUN_SEEN.load(Relaxed); let aa=V41_APPLY_ARG_SEEN.load(Relaxed); let c=V41_CANON_SEEN.load(Relaxed);
 let ef=V41_EMPTY_FORCE.load(Relaxed); let eaf=V41_EMPTY_APPLY_FUN.load(Relaxed); let eaa=V41_EMPTY_APPLY_ARG.load(Relaxed); let ec=V41_EMPTY_CANON.load(Relaxed);
 eprintln!("V41_BVAR_LIFETIME mk_calls={} mk_hits={} mk_news={} force={} apply_fun={} apply_arg={} canon={} empty_force={} empty_apply_fun={} empty_apply_arg={} empty_canon={}",calls,hits,news,f,af,aa,c,ef,eaf,eaa,ec);
 if calls!=0 { eprintln!("V41_MK_HIT_PCT={:.4}%",100.0*hits as f64/calls as f64); eprintln!("V41_MK_NEW_PCT={:.4}%",100.0*news as f64/calls as f64); }
 let total=f+af+aa+c; if total!=0 { eprintln!("V41_FORCE_SHARE={:.4}%",100.0*f as f64/total as f64); eprintln!("V41_APPLY_FUN_SHARE={:.4}%",100.0*af as f64/total as f64); eprintln!("V41_APPLY_ARG_SHARE={:.4}%",100.0*aa as f64/total as f64); eprintln!("V41_CANON_SHARE={:.4}%",100.0*c as f64/total as f64); }
 eprintln!("V41_RULE=census only; no BVar elimination is licensed without exact semantic replay of a concrete producer-consumer fusion");
}
'''
assert s.count(anchor)==1
s=s.replace(anchor,anchor+insert,1)
# Producer instrumentation.
old="""    pub(crate) fn mk_bvar_hc(&mut self, level: u32, ty: V<'t>) -> V<'t> {
        let key = (level, ty as *const Value<'t> as usize);
        if let Some(v) = self.tc_cache.bvar_hc.get(&key) {
            return v;
        }"""
new="""    pub(crate) fn mk_bvar_hc(&mut self, level: u32, ty: V<'t>) -> V<'t> {
        V41_MK_CALLS.fetch_add(1, Relaxed);
        let key = (level, ty as *const Value<'t> as usize);
        if let Some(v) = self.tc_cache.bvar_hc.get(&key) {
            V41_MK_HITS.fetch_add(1, Relaxed);
            return v;
        }
        V41_MK_NEWS.fetch_add(1, Relaxed);"""
assert s.count(old)==1
s=s.replace(old,new,1)
# Consumer instrumentation. Exact signatures are asserted to avoid silent drift.
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {
        if matches!(v, Value::Pi { .. }) { return v; }"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {
        v41_consume(v, 0);
        if matches!(v, Value::Pi { .. }) { return v; }"""
assert s.count(old)==1;s=s.replace(old,new,1)
old="""    pub(crate) fn apply(&mut self, depth: u32, f: V<'t>, a: V<'t>) -> V<'t> {
        match f {"""
new="""    pub(crate) fn apply(&mut self, depth: u32, f: V<'t>, a: V<'t>) -> V<'t> {
        v41_consume(f, 1); v41_consume(a, 2);
        match f {"""
assert s.count(old)==1;s=s.replace(old,new,1)
# canonicalize_for_spine is a major BVar consumer in rigid construction; inject after signature regardless of inline annotation.
needle="fn canonicalize_for_spine(&mut self, v: V<'t>) -> V<'t> {"
assert s.count(needle)==1
s=s.replace(needle,needle+"\n        v41_consume(v, 3);",1)
p.write_text(s)

p=Path('/tmp/v41-census/src/tc.rs');s=p.read_text()
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
        crate::eval::v41_report();
    }"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY

cat >/tmp/v41-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
for d in /tmp/v41-base /tmp/v41-census; do (cd "$d" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked); done
cp /tmp/v41-base/target/release/sokonanoda /tmp/v41-base-bin
cp /tmp/v41-census/target/release/sokonanoda /tmp/v41-census-bin
git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v41-arena
cd /tmp/v41-arena
nix develop -c ./lka.py build-test mathlib
/tmp/v41-base-bin /tmp/v41-config.json < _build/tests/mathlib.ndjson >/tmp/v41-base.out 2>/tmp/v41-base.err
/tmp/v41-census-bin /tmp/v41-config.json < _build/tests/mathlib.ndjson >/tmp/v41-census.out 2>/tmp/v41-census.err
cmp /tmp/v41-base.out /tmp/v41-census.out
echo V41_MATHLIB_SEMANTIC_REPLAY=EXACT
grep '^V41_' /tmp/v41-census.err | tee /tmp/v41-census.txt
python3 - <<'PY' | tee /tmp/v41-decision.txt
import re
s=open('/tmp/v41-census.txt').read()
m=re.search(r'V41_BVAR_LIFETIME mk_calls=(\d+) mk_hits=(\d+) mk_news=(\d+) force=(\d+) apply_fun=(\d+) apply_arg=(\d+) canon=(\d+)',s); assert m
calls,hits,news,f,af,aa,c=map(int,m.groups())
total=f+af+aa+c
print(f'V41_HIT_RATE={100*hits/calls if calls else 0:.4f}%')
print(f'V41_NEW_RATE={100*news/calls if calls else 0:.4f}%')
shares={'force':f,'apply_fun':af,'apply_arg':aa,'canon':c}
name,val=max(shares.items(),key=lambda kv:kv[1])
share=100*val/total if total else 0
print(f'V41_DOMINANT_CONSUMER={name} {share:.4f}%')
if news/calls >= .40 if calls else False:
    print('DECISION=V41_CREATION_FRAGMENTATION_HIGH__DECOMPOSE_BVAR_CREATION_ORIGIN')
elif share>=50:
    print('DECISION=V41_CONSUMER_CONCENTRATED__BUILD_EXACT_PRODUCER_CONSUMER_FUSION_FOR_DOMINANT_PATH')
else:
    print('DECISION=V41_BVAR_LIFETIME_FRAGMENTED__RETURN_TO_HIGHER_VALUE_DOMAIN_TRAJECTORY')
PY
