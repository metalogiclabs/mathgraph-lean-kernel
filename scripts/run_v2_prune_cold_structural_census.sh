#!/usr/bin/env bash
set -euxo pipefail

V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
rm -rf /tmp/prune-census /tmp/arena-prune /tmp/v2-prune
mkdir -p /tmp/prune-census

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/arena-prune
cd /tmp/arena-prune
for t in init-prelude init std mathlib; do
  nix develop -c ./lka.py build-test "$t"
done

cd "$GITHUB_WORKSPACE"
git worktree add /tmp/v2-prune "$V2"
cd /tmp/v2-prune

python3 - <<'PY'
from pathlib import Path
p=Path('src/eval.rs')
s=p.read_text()
anchor='use std::collections::hash_map::Entry;\n'
insert=r'''
use std::sync::atomic::{AtomicU64, Ordering};

// Sample 1/1024 structural prune events to keep the census cheap enough for
// full Mathlib while preserving a large, deterministic sample.
static PC_COLD_SAMPLE: AtomicU64 = AtomicU64::new(0);
static PC_SRC_CONS: AtomicU64 = AtomicU64::new(0);
static PC_SRC_FRAMED: AtomicU64 = AtomicU64::new(0);
static PC_N0: AtomicU64 = AtomicU64::new(0);
static PC_N1: AtomicU64 = AtomicU64::new(0);
static PC_N2: AtomicU64 = AtomicU64::new(0);
static PC_N34: AtomicU64 = AtomicU64::new(0);
static PC_N58: AtomicU64 = AtomicU64::new(0);
static PC_N916: AtomicU64 = AtomicU64::new(0);
static PC_N17P: AtomicU64 = AtomicU64::new(0);
static PC_DEPTH01: AtomicU64 = AtomicU64::new(0);
static PC_DEPTH24: AtomicU64 = AtomicU64::new(0);
static PC_DEPTH58: AtomicU64 = AtomicU64::new(0);
static PC_DEPTH916: AtomicU64 = AtomicU64::new(0);
static PC_DEPTH17P: AtomicU64 = AtomicU64::new(0);
static PC_POP_IN_SUM: AtomicU64 = AtomicU64::new(0);
static PC_POP_OUT_SUM: AtomicU64 = AtomicU64::new(0);
static PC_FRAME_SAMPLE: AtomicU64 = AtomicU64::new(0);
static PC_FRAME_HIT: AtomicU64 = AtomicU64::new(0);
static PC_FRAME_MISS: AtomicU64 = AtomicU64::new(0);

#[inline]
fn pc_inc(x: &AtomicU64) { x.fetch_add(1, Ordering::Relaxed); }

pub fn dump_prune_census() {
    let g = |x: &AtomicU64| x.load(Ordering::Relaxed);
    eprintln!("PRUNE_CENSUS cold_sample={} src_cons={} src_framed={} n0={} n1={} n2={} n3_4={} n5_8={} n9_16={} n17p={} depth0_1={} depth2_4={} depth5_8={} depth9_16={} depth17p={} pop_in_sum={} pop_out_sum={} frame_sample={} frame_hit={} frame_miss={}",
        g(&PC_COLD_SAMPLE), g(&PC_SRC_CONS), g(&PC_SRC_FRAMED), g(&PC_N0), g(&PC_N1), g(&PC_N2), g(&PC_N34), g(&PC_N58), g(&PC_N916), g(&PC_N17P),
        g(&PC_DEPTH01), g(&PC_DEPTH24), g(&PC_DEPTH58), g(&PC_DEPTH916), g(&PC_DEPTH17P), g(&PC_POP_IN_SUM), g(&PC_POP_OUT_SUM),
        g(&PC_FRAME_SAMPLE), g(&PC_FRAME_HIT), g(&PC_FRAME_MISS));
}
'''
assert anchor in s
s=s.replace(anchor, anchor+insert, 1)

# Sample frame-intern economics independently by the already-computed hash.
old='''        let lsub_addr = lsub.map_or(0, |l| l as *const value::LevelSub<'t> as usize);\n        if let Some(e) = self.tc_cache.frames.find(hash, |e: &E<'t>| match e {\n'''
new='''        let lsub_addr = lsub.map_or(0, |l| l as *const value::LevelSub<'t> as usize);\n        let pc_frame_sample = (hash & 1023) == 0;\n        if pc_frame_sample { pc_inc(&PC_FRAME_SAMPLE); }\n        if let Some(e) = self.tc_cache.frames.find(hash, |e: &E<'t>| match e {\n'''
assert old in s
s=s.replace(old,new,1)
old='''        }) {\n            return e;\n        }\n        let len = 64 - mask.leading_zeros();\n'''
new='''        }) {\n            if pc_frame_sample { pc_inc(&PC_FRAME_HIT); }\n            return e;\n        }\n        if pc_frame_sample { pc_inc(&PC_FRAME_MISS); }\n        let len = 64 - mask.leading_zeros();\n'''
assert old in s
s=s.replace(old,new,1)

# Mark a deterministic sample at cold-prune entry and source representation.
old='''    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {\n        let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];\n'''
new='''    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {\n        let pc_sample = (slot & 1023) == 0;\n        if pc_sample {\n            pc_inc(&PC_COLD_SAMPLE);\n            PC_POP_IN_SUM.fetch_add(mask.count_ones() as u64, Ordering::Relaxed);\n            match e {\n                value::Env::Cons { .. } => pc_inc(&PC_SRC_CONS),\n                value::Env::Framed { .. } => pc_inc(&PC_SRC_FRAMED),\n                value::Env::Nil { .. } => {}\n            }\n        }\n        let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];\n'''
assert old in s
s=s.replace(old,new,1)

old='''        let slots: &[V<'t>] = unsafe { std::slice::from_raw_parts(buf.as_ptr().cast::<V<'t>>(), n) };\n        let lsub = e.lsub();\n'''
new='''        if pc_sample {\n            match n {\n                0 => pc_inc(&PC_N0), 1 => pc_inc(&PC_N1), 2 => pc_inc(&PC_N2),\n                3..=4 => pc_inc(&PC_N34), 5..=8 => pc_inc(&PC_N58),\n                9..=16 => pc_inc(&PC_N916), _ => pc_inc(&PC_N17P),\n            }\n            match consumed {\n                0..=1 => pc_inc(&PC_DEPTH01), 2..=4 => pc_inc(&PC_DEPTH24),\n                5..=8 => pc_inc(&PC_DEPTH58), 9..=16 => pc_inc(&PC_DEPTH916),\n                _ => pc_inc(&PC_DEPTH17P),\n            }\n            PC_POP_OUT_SUM.fetch_add(out_mask.count_ones() as u64, Ordering::Relaxed);\n        }\n        let slots: &[V<'t>] = unsafe { std::slice::from_raw_parts(buf.as_ptr().cast::<V<'t>>(), n) };\n        let lsub = e.lsub();\n'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s)

p=Path('src/main.rs')
s=p.read_text()
old='''    export_file.check_all_declars();\n    // Pretty print as necessary\n'''
new='''    export_file.check_all_declars();\n    sokonanoda::eval::dump_prune_census();\n    // Pretty print as necessary\n'''
assert old in s
p.write_text(s.replace(old,new,1))
PY

cargo test --release --locked
cargo build --release --locked

cat >/tmp/prune-census/checker.json <<'EOF'
{
  "use_stdin": true,
  "nat_extension": true,
  "string_extension": true,
  "unpermitted_axiom_hard_error": false,
  "unsafe_permit_all_axioms": true,
  "num_threads": 4,
  "print_success_message": false
}
EOF

# Run independent processes so each workload has independent counters.
for t in init std mathlib; do
  f="/tmp/arena-prune/_build/tests/$t.ndjson"
  timeout 1200 target/release/sokonanoda /tmp/prune-census/checker.json < "$f" \
    >"/tmp/prune-census/$t.out" 2>"/tmp/prune-census/$t.err"
  grep 'PRUNE_CENSUS' "/tmp/prune-census/$t.err" | tail -1 >"/tmp/prune-census/$t.census"
done

python3 - <<'PY' | tee /tmp/prune-census/summary.txt
from pathlib import Path
for t in ['init','std','mathlib']:
    line=Path(f'/tmp/prune-census/{t}.census').read_text().strip()
    kv={}
    for tok in line.split()[1:]:
        k,v=tok.split('=',1); kv[k]=int(v)
    n=kv['cold_sample']; fs=kv['frame_sample']
    print('\nWORKLOAD',t)
    print(line)
    if n:
        print('cold_source_cons_pct',100*kv['src_cons']/n)
        print('cold_source_framed_pct',100*kv['src_framed']/n)
        print('mean_selected_slots',kv['pop_out_sum']/n)
        print('mean_requested_popcount',kv['pop_in_sum']/n)
        print('selected_le2_pct',100*(kv['n0']+kv['n1']+kv['n2'])/n)
        print('depth_le4_pct',100*(kv['depth0_1']+kv['depth2_4'])/n)
    if fs:
        print('frame_intern_hit_pct',100*kv['frame_hit']/fs)
        print('frame_intern_miss_pct',100*kv['frame_miss']/fs)

# Precommitted interpretation gates, not a promotion gate.
m=Path('/tmp/prune-census/mathlib.census').read_text().strip()
kv={tok.split('=',1)[0]:int(tok.split('=',1)[1]) for tok in m.split()[1:]}
n=kv['cold_sample']; fs=kv['frame_sample']
small=(kv['n0']+kv['n1']+kv['n2'])/n if n else 0
shallow=(kv['depth0_1']+kv['depth2_4'])/n if n else 0
hit=kv['frame_hit']/fs if fs else 0
print('\nMATHLIB_DECISION_INPUTS')
print(f'small_projection_le2={small:.6f}')
print(f'shallow_depth_le4={shallow:.6f}')
print(f'frame_intern_hit={hit:.6f}')
if small >= .70 and hit >= .50:
    print('DECISION=DIRECT_SMALL_PROJECTION_PLUS_FAST_FRAME_INTERN_AB')
elif hit >= .70:
    print('DECISION=FRAME_INTERN_FASTPATH_AB')
elif small >= .70:
    print('DECISION=DIRECT_SMALL_PROJECTION_AB')
else:
    print('DECISION=REPRESENTATION_LEVEL_ENV_REDESIGN_REQUIRED')
PY
