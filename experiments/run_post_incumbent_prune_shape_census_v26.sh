#!/usr/bin/env bash
set -euxo pipefail

# Reconstruct the verified Pi+v18 incumbent exactly, then instrument only the
# remaining cold-prune path. This is a census, not a performance candidate.
bash experiments/run_post_compound_self_cost_atlas_v21.sh

rm -rf /tmp/v26-census /tmp/v26-target
cp -a /tmp/v21-compound /tmp/v26-census
cd /tmp/v26-census

python3 - <<'PY'
from pathlib import Path
p=Path('src/eval.rs')
s=p.read_text()
anchor='use std::collections::hash_map::Entry;\n'
insert=r'''
use std::sync::atomic::{AtomicU64, Ordering};
static V26_COLD: AtomicU64 = AtomicU64::new(0);
static V26_SRC_CONS: AtomicU64 = AtomicU64::new(0);
static V26_SRC_FRAMED: AtomicU64 = AtomicU64::new(0);
static V26_PC1: AtomicU64 = AtomicU64::new(0);
static V26_PC2: AtomicU64 = AtomicU64::new(0);
static V26_PC34: AtomicU64 = AtomicU64::new(0);
static V26_PC5P: AtomicU64 = AtomicU64::new(0);
static V26_CS0: AtomicU64 = AtomicU64::new(0);
static V26_CS1: AtomicU64 = AtomicU64::new(0);
static V26_CS2: AtomicU64 = AtomicU64::new(0);
static V26_CS34: AtomicU64 = AtomicU64::new(0);
static V26_CS5P: AtomicU64 = AtomicU64::new(0);
static V26_END_FRAMED: AtomicU64 = AtomicU64::new(0);
static V26_END_NIL: AtomicU64 = AtomicU64::new(0);
static V26_FRAMED_PC1: AtomicU64 = AtomicU64::new(0);
static V26_FRAMED_PC2: AtomicU64 = AtomicU64::new(0);
static V26_FRAMED_PC34: AtomicU64 = AtomicU64::new(0);
static V26_FRAMED_PC5P: AtomicU64 = AtomicU64::new(0);
#[inline] fn v26i(x:&AtomicU64){x.fetch_add(1,Ordering::Relaxed);}
pub fn dump_v26_prune_shape(){
 let g=|x:&AtomicU64|x.load(Ordering::Relaxed);
 eprintln!("V26_PRUNE_SHAPE cold={} src_cons={} src_framed={} pc1={} pc2={} pc3_4={} pc5p={} cs0={} cs1={} cs2={} cs3_4={} cs5p={} end_framed={} end_nil={} framed_pc1={} framed_pc2={} framed_pc3_4={} framed_pc5p={}",
 g(&V26_COLD),g(&V26_SRC_CONS),g(&V26_SRC_FRAMED),g(&V26_PC1),g(&V26_PC2),g(&V26_PC34),g(&V26_PC5P),g(&V26_CS0),g(&V26_CS1),g(&V26_CS2),g(&V26_CS34),g(&V26_CS5P),g(&V26_END_FRAMED),g(&V26_END_NIL),g(&V26_FRAMED_PC1),g(&V26_FRAMED_PC2),g(&V26_FRAMED_PC34),g(&V26_FRAMED_PC5P));
}
'''
assert anchor in s
s=s.replace(anchor,anchor+insert,1)
old="""    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {
        let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];"""
new="""    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {
        let v26_sample = (slot & 255) == 0;
        if v26_sample {
            v26i(&V26_COLD);
            match e { value::Env::Cons {..} => v26i(&V26_SRC_CONS), value::Env::Framed {..} => v26i(&V26_SRC_FRAMED), value::Env::Nil {..} => {} }
            match mask.count_ones() { 1=>v26i(&V26_PC1), 2=>v26i(&V26_PC2), 3..=4=>v26i(&V26_PC34), _=>v26i(&V26_PC5P) }
        }
        let mut v26_cons_steps=0u32;
        let mut v26_end_framed=false;
        let mut v26_end_nil=false;
        let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];"""
assert s.count(old)==1
s=s.replace(old,new,1)
old="""                value::Env::Nil { .. } => break,
                value::Env::Framed { mask: fmask, slots, .. } => {"""
new="""                value::Env::Nil { .. } => { v26_end_nil=true; break },
                value::Env::Framed { mask: fmask, slots, .. } => {
                    v26_end_framed=true;"""
assert s.count(old)==1
s=s.replace(old,new,1)
old="""                value::Env::Cons { v, parent, .. } => {
                    if rem & 1 != 0 {"""
new="""                value::Env::Cons { v, parent, .. } => {
                    v26_cons_steps += 1;
                    if rem & 1 != 0 {"""
assert s.count(old)==1
s=s.replace(old,new,1)
old="""        let slots: &[V<'t>] = unsafe { std::slice::from_raw_parts(buf.as_ptr().cast::<V<'t>>(), n) };
        let lsub = e.lsub();"""
new="""        if v26_sample {
            match v26_cons_steps { 0=>v26i(&V26_CS0),1=>v26i(&V26_CS1),2=>v26i(&V26_CS2),3..=4=>v26i(&V26_CS34),_=>v26i(&V26_CS5P) }
            if v26_end_framed {
                v26i(&V26_END_FRAMED);
                match mask.count_ones() {1=>v26i(&V26_FRAMED_PC1),2=>v26i(&V26_FRAMED_PC2),3..=4=>v26i(&V26_FRAMED_PC34),_=>v26i(&V26_FRAMED_PC5P)}
            }
            if v26_end_nil { v26i(&V26_END_NIL); }
        }
        let slots: &[V<'t>] = unsafe { std::slice::from_raw_parts(buf.as_ptr().cast::<V<'t>>(), n) };
        let lsub = e.lsub();"""
assert s.count(old)==1
s=s.replace(old,new,1)
p.write_text(s)

p=Path('src/main.rs'); s=p.read_text()
old='''    export_file.check_all_declars();\n    // Pretty print as necessary\n'''
new='''    export_file.check_all_declars();\n    sokonanoda::eval::dump_v26_prune_shape();\n    // Pretty print as necessary\n'''
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
print('V26_CENSUS_PATCH=APPLIED')
PY

cargo test --release --locked
CARGO_TARGET_DIR=/tmp/v26-target RUSTFLAGS='-C target-cpu=x86-64' cargo build --release --locked
cp /tmp/v26-target/release/sokonanoda /tmp/v26-bin

cd /tmp/v21-arena
F=_build/tests/perf/grind-ring-5.ndjson
/tmp/v26-bin /tmp/v21-checker.json < "$F" >/tmp/v26.out 2>/tmp/v26.err
cmp /tmp/v21-compound.out /tmp/v26.out
echo V26_SEMANTIC_REPLAY=EXACT | tee /tmp/v26-semantic.txt
grep 'V26_PRUNE_SHAPE' /tmp/v26.err | tail -1 | tee /tmp/v26-shape.txt

python3 - <<'PY' | tee /tmp/v26-decision.txt
from pathlib import Path
line=Path('/tmp/v26-shape.txt').read_text().strip()
kv={}
for tok in line.split()[1:]:
 k,v=tok.split('=',1); kv[k]=int(v)
n=kv['cold']
print('V26_SEMANTIC_REPLAY=EXACT')
for k in ['src_cons','src_framed','pc1','pc2','pc3_4','pc5p','cs0','cs1','cs2','cs3_4','cs5p','end_framed','end_nil']:
 print(f'{k.upper()}_PCT={100*kv[k]/n:.4f}')
short=(kv['cs0']+kv['cs1']+kv['cs2']+kv['cs3_4'])/n
fr=kv['end_framed']/n
print(f'CONS_STEPS_LE4_PCT={100*short:.4f}')
print(f'ENDS_IN_FRAMED_PCT={100*fr:.4f}')
# Precommitted routing: specialize only a large structural basin; otherwise census deeper.
if short >= .70 and fr >= .50:
 print('DECISION=V26_ROUTE__SHORT_CONS_TO_FRAMED_FASTPATH')
elif kv['src_framed']/n >= .50:
 print('DECISION=V26_ROUTE__DIRECT_FRAMED_SUBPROJECTION_FASTPATH')
elif short >= .70:
 print('DECISION=V26_ROUTE__SHORT_CONS_PREFIX_FASTPATH')
else:
 print('DECISION=V26_ROUTE__DEEPER_PATH_SHAPE_CENSUS')
PY
