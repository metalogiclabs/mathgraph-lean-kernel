#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v34-base /tmp/v34-census /tmp/v34-arena

git worktree add /tmp/v34-base "$BASE"
git worktree add /tmp/v34-census "$BASE"

# Verified v29 wall-time incumbent: Pi-only force collapse, applied identically.
for arm in base census; do
python3 - "$arm" <<'PY'
from pathlib import Path
import sys
p=Path(f'/tmp/v34-{sys.argv[1]}/src/eval.rs'); s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {
        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {
        if matches!(v, Value::Pi { .. }) { return v; }
        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY
done

# Instrument only already-native conversion/value-domain distinctions.
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v34-census/src/conv.rs'); s=p.read_text()
anchor='use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};\n'
probe=r'''use std::sync::atomic::{AtomicU64, Ordering};
static V34_UNIFY: AtomicU64 = AtomicU64::new(0);
static V34_PTR: AtomicU64 = AtomicU64::new(0);
static V34_GENERAL: AtomicU64 = AtomicU64::new(0);
static V34_UF_HIT: AtomicU64 = AtomicU64::new(0);
static V34_NEG_HIT: AtomicU64 = AtomicU64::new(0);
static V34_NO_CACHE: AtomicU64 = AtomicU64::new(0);
static V34_DIRECT_HIT: AtomicU64 = AtomicU64::new(0);
static V34_COLD: AtomicU64 = AtomicU64::new(0);
static V34_PI_PI: AtomicU64 = AtomicU64::new(0);
static V34_LAM_LAM: AtomicU64 = AtomicU64::new(0);
static V34_UNFOLD_UNFOLD: AtomicU64 = AtomicU64::new(0);
static V34_RIGID_RIGID: AtomicU64 = AtomicU64::new(0);
static V34_UNFOLD_MIX: AtomicU64 = AtomicU64::new(0);

pub fn report_v34() {
    if std::env::var_os("MATHGRAPH_V34_CENSUS").is_none() { return; }
    eprintln!("V34 unify={} ptr={} general={} uf_hit={} neg_hit={} no_cache={} direct_hit={} cold={} pi_pi={} lam_lam={} unfold_unfold={} rigid_rigid={} unfold_mix={}",
        V34_UNIFY.load(Ordering::Relaxed), V34_PTR.load(Ordering::Relaxed), V34_GENERAL.load(Ordering::Relaxed),
        V34_UF_HIT.load(Ordering::Relaxed), V34_NEG_HIT.load(Ordering::Relaxed), V34_NO_CACHE.load(Ordering::Relaxed),
        V34_DIRECT_HIT.load(Ordering::Relaxed), V34_COLD.load(Ordering::Relaxed), V34_PI_PI.load(Ordering::Relaxed),
        V34_LAM_LAM.load(Ordering::Relaxed), V34_UNFOLD_UNFOLD.load(Ordering::Relaxed), V34_RIGID_RIGID.load(Ordering::Relaxed),
        V34_UNFOLD_MIX.load(Ordering::Relaxed));
}
'''
assert anchor in s
s=s.replace(anchor,anchor+probe,1)

old="""    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
        let x = self.force_thunk(depth, x);
        let y = self.force_thunk(depth, y);
        if std::ptr::eq(x, y) {
            return true;
        }
        self.unify_general::<RIGID>(depth, x, y)
    }"""
new="""    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
        V34_UNIFY.fetch_add(1, Ordering::Relaxed);
        let x = self.force_thunk(depth, x);
        let y = self.force_thunk(depth, y);
        if std::ptr::eq(x, y) {
            V34_PTR.fetch_add(1, Ordering::Relaxed);
            return true;
        }
        self.unify_general::<RIGID>(depth, x, y)
    }"""
assert old in s
s=s.replace(old,new,1)

sig="""    fn unify_general<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
"""
assert sig in s
s=s.replace(sig,sig+'        V34_GENERAL.fetch_add(1, Ordering::Relaxed);\n',1)
s=s.replace("""            if self.tc_cache.conv_uf.equiv(xa, ya) {
                return true;
            }""","""            if self.tc_cache.conv_uf.equiv(xa, ya) {
                V34_UF_HIT.fetch_add(1, Ordering::Relaxed);
                return true;
            }""",1)
s=s.replace("""                if self.tc_cache.conv_cache_neg.contains(&cache_key) {
                    return false;
                }""","""                if self.tc_cache.conv_cache_neg.contains(&cache_key) {
                    V34_NEG_HIT.fetch_add(1, Ordering::Relaxed);
                    return false;
                }""",1)

sig="""    fn unify_no_cache<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
"""
assert sig in s
s=s.replace(sig,sig+'        V34_NO_CACHE.fetch_add(1, Ordering::Relaxed);\n',1)
old="""        if self.unify_direct::<RIGID>(depth, t, t2) {
            return true;
        }
        self.unify_cold::<RIGID>(depth, t, t2)
"""
new="""        if self.unify_direct::<RIGID>(depth, t, t2) {
            V34_DIRECT_HIT.fetch_add(1, Ordering::Relaxed);
            return true;
        }
        V34_COLD.fetch_add(1, Ordering::Relaxed);
        self.unify_cold::<RIGID>(depth, t, t2)
"""
assert old in s
s=s.replace(old,new,1)

sig="""    fn unify_direct<const RIGID: bool>(&mut self, depth: u32, t: V<'t>, t2: V<'t>) -> bool {
        match (t, t2) {
"""
new="""    fn unify_direct<const RIGID: bool>(&mut self, depth: u32, t: V<'t>, t2: V<'t>) -> bool {
        match (t, t2) {
            (Value::Pi { .. }, Value::Pi { .. }) => { V34_PI_PI.fetch_add(1, Ordering::Relaxed); }
            (Value::Lam { .. }, Value::Lam { .. }) => { V34_LAM_LAM.fetch_add(1, Ordering::Relaxed); }
            (Value::Unfold { .. }, Value::Unfold { .. }) => { V34_UNFOLD_UNFOLD.fetch_add(1, Ordering::Relaxed); }
            (Value::Rigid { .. }, Value::Rigid { .. }) => { V34_RIGID_RIGID.fetch_add(1, Ordering::Relaxed); }
            (Value::Unfold { .. }, _) | (_, Value::Unfold { .. }) => { V34_UNFOLD_MIX.fetch_add(1, Ordering::Relaxed); }
            _ => {}
        }
        match (t, t2) {
"""
assert sig in s
s=s.replace(sig,new,1)
p.write_text(s)

p=Path('/tmp/v34-census/src/main.rs'); s=p.read_text()
old='''    // Pretty print as necessary
    let pp_errs = export_file.pp_selected_declars(pp_destination.as_mut());'''
new='''    sokonanoda::conv::report_v34();
    // Pretty print as necessary
    let pp_errs = export_file.pp_selected_declars(pp_destination.as_mut());'''
assert old in s
p.write_text(s.replace(old,new,1))
PY

cat >/tmp/v34-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

for arm in base census; do
  (cd "/tmp/v34-$arm" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
  cp "/tmp/v34-$arm/target/release/sokonanoda" "/tmp/v34-$arm-bin"
done

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v34-arena
cd /tmp/v34-arena
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t"; done

# Semantic differential first on Std/Cedar.
for t in std cedar; do
  /tmp/v34-base-bin /tmp/v34-config.json < "_build/tests/$t.ndjson" >"/tmp/v34-$t-base.out" 2>"/tmp/v34-$t-base.err"
  MATHGRAPH_V34_CENSUS=1 /tmp/v34-census-bin /tmp/v34-config.json < "_build/tests/$t.ndjson" >"/tmp/v34-$t-census.out" 2>"/tmp/v34-$t-census.err"
  cmp "/tmp/v34-$t-base.out" "/tmp/v34-$t-census.out"
  echo "V34_${t^^}_SEMANTIC_REPLAY=EXACT"
done

: >/tmp/v34-census.txt
for t in std cedar mathlib; do
  echo "V34_TEST=$t" | tee -a /tmp/v34-census.txt
  MATHGRAPH_V34_CENSUS=1 /usr/bin/time -f 'V34_TIME wall=%e user=%U sys=%S rss=%M' /tmp/v34-census-bin /tmp/v34-config.json < "_build/tests/$t.ndjson" >/dev/null 2>"/tmp/v34-$t-count.err"
  grep '^V34' "/tmp/v34-$t-count.err" | tee -a /tmp/v34-census.txt
done

python3 - <<'PY' | tee /tmp/v34-decision.txt
from pathlib import Path
import re
rows={}; cur=None
for line in Path('/tmp/v34-census.txt').read_text().splitlines():
    if line.startswith('V34_TEST='):
        cur=line.split('=',1)[1]; rows[cur]={}
    elif line.startswith('V34 unify='):
        rows[cur].update({k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)})
for t,r in rows.items():
    u=max(1,r.get('unify',0)); nc=max(1,r.get('no_cache',0))
    print(f'{t}: unify={r.get("unify",0):,} ptr={r.get("ptr",0):,} ({r.get("ptr",0)/u:.2%}) general={r.get("general",0):,} uf_hit={r.get("uf_hit",0):,} neg_hit={r.get("neg_hit",0):,}')
    print(f'{t}: no_cache={r.get("no_cache",0):,} direct_hit={r.get("direct_hit",0):,} cold={r.get("cold",0):,} cold/no_cache={r.get("cold",0)/nc:.2%}')
    print(f'{t}: pairs pi={r.get("pi_pi",0):,} lam={r.get("lam_lam",0):,} unfold={r.get("unfold_unfold",0):,} rigid={r.get("rigid_rigid",0):,} unfold_mix={r.get("unfold_mix",0):,}')
m=rows.get('mathlib') or rows.get('cedar') or {}
cands={
 'VALUE_SPINE_RIGID_CONTINUATION':m.get('rigid_rigid',0),
 'UNFOLD_VALUE_CONTINUATION':m.get('unfold_unfold',0)+m.get('unfold_mix',0),
 'BINDER_CLOSURE_CONTINUATION':m.get('pi_pi',0)+m.get('lam_lam',0),
 'CONVERSION_COLD_RESIDUAL':m.get('cold',0),
}
print('V34_ROUTING_COUNTS='+repr(sorted(cands.items(),key=lambda kv:kv[1],reverse=True)))
print('V34_ROUTE='+max(cands,key=cands.get))
print('V34_RULE=OPTIMIZE_ONLY_A_CONSEQUENCE_ALREADY_NATIVE_TO_THE_VALUE_DOMAIN')
print('V34_NEXT=build small independent candidate portfolio for routed native basin; exact Std+Cedar tournament before full Mathlib')
PY
