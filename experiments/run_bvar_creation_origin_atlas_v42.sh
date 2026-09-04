#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v42-base /tmp/v42-census /tmp/v42-arena

git worktree add /tmp/v42-base "$BASE"
git worktree add /tmp/v42-census "$BASE"

for d in /tmp/v42-base /tmp/v42-census; do
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
p=Path('/tmp/v42-census/src/eval.rs')
s=p.read_text()
s=s.replace('use std::cell::OnceCell;','use std::cell::OnceCell;\nuse std::collections::HashMap;\nuse std::sync::{Mutex, OnceLock};',1)
anchor='pub(crate) type SpineArgs'
insert=r'''type V42OriginMap = HashMap<(\'static str, u32), (u64,u64,u64)>;
static V42_ORIGINS: OnceLock<Mutex<V42OriginMap>> = OnceLock::new();
#[inline] fn v42_origins() -> &'static Mutex<V42OriginMap> { V42_ORIGINS.get_or_init(|| Mutex::new(HashMap::new())) }
#[inline] fn v42_record(file: &'static str, line:u32, hit:bool) {
    let mut m=v42_origins().lock().unwrap();
    let e=m.entry((file,line)).or_insert((0,0,0)); e.0+=1; if hit{e.1+=1}else{e.2+=1;}
}
pub(crate) fn v42_report(){
    let m=v42_origins().lock().unwrap();
    let mut rows:Vec<_>=m.iter().map(|(&(f,l),&(c,h,n))|(f,l,c,h,n)).collect(); rows.sort_by_key(|r|std::cmp::Reverse(r.4));
    let tc:u64=rows.iter().map(|r|r.2).sum(); let th:u64=rows.iter().map(|r|r.3).sum(); let tn:u64=rows.iter().map(|r|r.4).sum();
    eprintln!("V42_TOTAL calls={} hits={} news={} sites={}",tc,th,tn,rows.len());
    for (i,(f,l,c,h,n)) in rows.into_iter().take(20).enumerate(){let pct=if tn==0{0.0}else{100.0*n as f64/tn as f64};eprintln!("V42_SITE rank={} file={} line={} calls={} hits={} news={} new_share={:.4}%",i+1,f,l,c,h,n,pct);}
    eprintln!("V42_RULE=callsite atlas only; no elimination without exact replay of concrete origin-specific prototype");
}
'''
s=s.replace(anchor,insert+'\n'+anchor,1)
old="""    #[inline]
    pub(crate) fn mk_bvar_hc(&mut self, level: u32, ty: V<'t>) -> V<'t> {
        let key = (level, ty as *const Value<'t> as usize);
        if let Some(v) = self.tc_cache.bvar_hc.get(&key) {
            return v;
        }
        let empty = self.empty_spine();
        let v = value::mk_bvar_with_empty(self.arena, level, ty, empty);
        self.tc_cache.bvar_hc.insert(key, v);
        v
    }"""
new="""    #[inline]
    #[track_caller]
    pub(crate) fn mk_bvar_hc(&mut self, level: u32, ty: V<'t>) -> V<'t> {
        let loc=std::panic::Location::caller();
        let key = (level, ty as *const Value<'t> as usize);
        if let Some(v) = self.tc_cache.bvar_hc.get(&key) {
            v42_record(loc.file(),loc.line(),true);
            return v;
        }
        let empty = self.empty_spine();
        let v = value::mk_bvar_with_empty(self.arena, level, ty, empty);
        self.tc_cache.bvar_hc.insert(key, v);
        v42_record(loc.file(),loc.line(),false);
        v
    }"""
assert s.count(old)==1;s=s.replace(old,new,1);p.write_text(s)
p=Path('/tmp/v42-census/src/tc.rs');s=p.read_text();old="""    pub fn check_all_declars(&self) {
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
        crate::eval::v42_report();
    }""";assert s.count(old)==1;p.write_text(s.replace(old,new,1))
PY

cat >/tmp/v42-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
for d in /tmp/v42-base /tmp/v42-census; do (cd "$d" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked); done
cp /tmp/v42-base/target/release/sokonanoda /tmp/v42-base-bin
cp /tmp/v42-census/target/release/sokonanoda /tmp/v42-census-bin
git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v42-arena
cd /tmp/v42-arena
nix develop -c ./lka.py build-test mathlib
/tmp/v42-base-bin /tmp/v42-config.json < _build/tests/mathlib.ndjson >/tmp/v42-base.out 2>/tmp/v42-base.err
/tmp/v42-census-bin /tmp/v42-config.json < _build/tests/mathlib.ndjson >/tmp/v42-census.out 2>/tmp/v42-census.err
cmp /tmp/v42-base.out /tmp/v42-census.out
echo V42_MATHLIB_SEMANTIC_REPLAY=EXACT
grep '^V42_' /tmp/v42-census.err | tee /tmp/v42-census.txt
python3 - <<'PY' | tee /tmp/v42-decision.txt
import re
s=open('/tmp/v42-census.txt').read()
m=re.search(r'V42_TOTAL calls=(\d+) hits=(\d+) news=(\d+) sites=(\d+)',s);assert m
calls,hits,news,sites=map(int,m.groups())
rows=[]
for x in re.finditer(r'V42_SITE rank=(\d+) file=(\S+) line=(\d+) calls=(\d+) hits=(\d+) news=(\d+) new_share=([0-9.]+)%',s): rows.append((int(x.group(1)),x.group(2),int(x.group(3)),int(x.group(4)),int(x.group(5)),int(x.group(6)),float(x.group(7))))
assert rows
r=rows[0]
print(f'V42_DOMINANT_SITE={r[1]}:{r[2]}')
print(f'V42_DOMINANT_NEW_SHARE={r[6]:.4f}%')
if r[6]>=40: print('DECISION=V42_CONCENTRATED_CREATION_ORIGIN__BUILD_EXACT_ORIGIN_SPECIFIC_ELIMINATION_PROTOTYPE')
elif r[6]>=20: print('DECISION=V42_MATERIAL_CREATION_ORIGIN__DECOMPOSE_DOMINANT_CALLSITE_TRAJECTORY')
else: print('DECISION=V42_CREATION_ORIGINS_FRAGMENTED__RETURN_TO_HIGH_VOLUME_CONSUMER_TRAJECTORY')
PY
