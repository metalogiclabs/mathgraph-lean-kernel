#!/usr/bin/env bash
set -euxo pipefail
V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
rm -rf /tmp/v2 /tmp/arena

git worktree add /tmp/v2 "$V2"
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v2/src/conv.rs')
s=p.read_text()
anchor='use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};\n'
probe=r'''use std::sync::atomic::{AtomicU64, Ordering};
static MG_UNIFY: AtomicU64 = AtomicU64::new(0);
static MG_PTR_EQ: AtomicU64 = AtomicU64::new(0);
static MG_CACHE_POS: AtomicU64 = AtomicU64::new(0);
static MG_CACHE_NEG: AtomicU64 = AtomicU64::new(0);
static MG_UU: AtomicU64 = AtomicU64::new(0);
static MG_UU_HEAD_MATCH: AtomicU64 = AtomicU64::new(0);
static MG_UU_HEAD_MISMATCH: AtomicU64 = AtomicU64::new(0);
static MG_UU_HINT_LEFT: AtomicU64 = AtomicU64::new(0);
static MG_UU_HINT_RIGHT: AtomicU64 = AtomicU64::new(0);
static MG_UU_HINT_EQUAL: AtomicU64 = AtomicU64::new(0);
static MG_ONE_SIDED_UNFOLD: AtomicU64 = AtomicU64::new(0);
static MG_UNFOLD_PAIR: AtomicU64 = AtomicU64::new(0);
static MG_SPINE_PROBE: AtomicU64 = AtomicU64::new(0);
static MG_SPINE_PROBE_TRUE: AtomicU64 = AtomicU64::new(0);
static MG_PROOF_IRREL: AtomicU64 = AtomicU64::new(0);
static MG_PROOF_IRREL_TRUE: AtomicU64 = AtomicU64::new(0);
static MG_IOTA_PAIR: AtomicU64 = AtomicU64::new(0);
static MG_STRUCT_ETA: AtomicU64 = AtomicU64::new(0);

pub fn report_conversion_choice_census() {
    if std::env::var_os("MATHGRAPH_CONV_CENSUS").is_none() { return; }
    eprintln!("MG_CONV unify={} ptr_eq={} cache_pos={} cache_neg={} uu={} uu_head_match={} uu_head_mismatch={} hint_left={} hint_right={} hint_equal={} one_sided_unfold={} unfold_pair={} spine_probe={} spine_probe_true={} proof_irrel={} proof_irrel_true={} iota_pair={} struct_eta={}",
      MG_UNIFY.load(Ordering::Relaxed), MG_PTR_EQ.load(Ordering::Relaxed), MG_CACHE_POS.load(Ordering::Relaxed), MG_CACHE_NEG.load(Ordering::Relaxed),
      MG_UU.load(Ordering::Relaxed), MG_UU_HEAD_MATCH.load(Ordering::Relaxed), MG_UU_HEAD_MISMATCH.load(Ordering::Relaxed),
      MG_UU_HINT_LEFT.load(Ordering::Relaxed), MG_UU_HINT_RIGHT.load(Ordering::Relaxed), MG_UU_HINT_EQUAL.load(Ordering::Relaxed),
      MG_ONE_SIDED_UNFOLD.load(Ordering::Relaxed), MG_UNFOLD_PAIR.load(Ordering::Relaxed), MG_SPINE_PROBE.load(Ordering::Relaxed), MG_SPINE_PROBE_TRUE.load(Ordering::Relaxed),
      MG_PROOF_IRREL.load(Ordering::Relaxed), MG_PROOF_IRREL_TRUE.load(Ordering::Relaxed), MG_IOTA_PAIR.load(Ordering::Relaxed), MG_STRUCT_ETA.load(Ordering::Relaxed));
}
'''
assert anchor in s
s=s.replace(anchor,anchor+probe,1)

old='''    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {\n        let x = self.force_thunk(depth, x);\n        let y = self.force_thunk(depth, y);\n        if std::ptr::eq(x, y) {\n            return true;\n        }'''
new='''    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {\n        MG_UNIFY.fetch_add(1, Ordering::Relaxed);\n        let x = self.force_thunk(depth, x);\n        let y = self.force_thunk(depth, y);\n        if std::ptr::eq(x, y) {\n            MG_PTR_EQ.fetch_add(1, Ordering::Relaxed);\n            return true;\n        }'''
assert old in s; s=s.replace(old,new,1)

old='''            if self.tc_cache.conv_uf.equiv(xa, ya) {\n                return true;\n            }'''
new='''            if self.tc_cache.conv_uf.equiv(xa, ya) {\n                MG_CACHE_POS.fetch_add(1, Ordering::Relaxed);\n                return true;\n            }'''
assert old in s; s=s.replace(old,new,1)
old='''                if self.tc_cache.conv_cache_neg.contains(&cache_key) {\n                    return false;\n                }'''
new='''                if self.tc_cache.conv_cache_neg.contains(&cache_key) {\n                    MG_CACHE_NEG.fetch_add(1, Ordering::Relaxed);\n                    return false;\n                }'''
assert old in s; s=s.replace(old,new,1)

needle='''            (\n                Value::Unfold { head: UnfoldHead { name: nx, levels: lx }, spine: sx, .. },\n                Value::Unfold { head: UnfoldHead { name: ny, levels: ly }, spine: sy, .. },\n            ) => {\n                let heads_match = nx == ny && self.ctx.eq_antisymm_many(*lx, *ly);'''
repl='''            (\n                Value::Unfold { head: UnfoldHead { name: nx, levels: lx }, spine: sx, .. },\n                Value::Unfold { head: UnfoldHead { name: ny, levels: ly }, spine: sy, .. },\n            ) => {\n                MG_UU.fetch_add(1, Ordering::Relaxed);\n                let heads_match = nx == ny && self.ctx.eq_antisymm_many(*lx, *ly);\n                if heads_match { MG_UU_HEAD_MATCH.fetch_add(1, Ordering::Relaxed); } else { MG_UU_HEAD_MISMATCH.fetch_add(1, Ordering::Relaxed); }'''
assert needle in s; s=s.replace(needle,repl,1)

old='''                    if lh.is_lt(&rh) {\n                        let v2 = self.unfold_value(depth, t2);'''
new='''                    if lh.is_lt(&rh) {\n                        MG_UU_HINT_RIGHT.fetch_add(1, Ordering::Relaxed);\n                        let v2 = self.unfold_value(depth, t2);'''
assert old in s; s=s.replace(old,new,1)
old='''                    } else if rh.is_lt(&lh) {\n                        let v1 = self.unfold_value(depth, t);'''
new='''                    } else if rh.is_lt(&lh) {\n                        MG_UU_HINT_LEFT.fetch_add(1, Ordering::Relaxed);\n                        let v1 = self.unfold_value(depth, t);'''
assert old in s; s=s.replace(old,new,1)
old='''                    } else {\n                        self.unfold_pair(depth, t, t2)\n                    }'''
new='''                    } else {\n                        MG_UU_HINT_EQUAL.fetch_add(1, Ordering::Relaxed);\n                        self.unfold_pair(depth, t, t2)\n                    }'''
assert old in s; s=s.replace(old,new,1)

s=s.replace('''            (Value::Unfold { .. }, _) if RIGID => {\n''','''            (Value::Unfold { .. }, _) if RIGID => {\n                MG_ONE_SIDED_UNFOLD.fetch_add(1, Ordering::Relaxed);\n''',1)
s=s.replace('''            (_, Value::Unfold { .. }) if RIGID => {\n''','''            (_, Value::Unfold { .. }) if RIGID => {\n                MG_ONE_SIDED_UNFOLD.fetch_add(1, Ordering::Relaxed);\n''',1)

old='''    fn unfold_pair(&mut self, depth: u32, t: V<'t>, t2: V<'t>) -> bool {\n        let v1 = self.unfold_value(depth, t);'''
new='''    fn unfold_pair(&mut self, depth: u32, t: V<'t>, t2: V<'t>) -> bool {\n        MG_UNFOLD_PAIR.fetch_add(1, Ordering::Relaxed);\n        let v1 = self.unfold_value(depth, t);'''
assert old in s; s=s.replace(old,new,1)

old='''    fn spine_probe(&mut self, depth: u32, sx: S<'t>, sy: S<'t>, sig: Sig, limit: u32) -> bool {\n        if std::ptr::eq(sx, sy) {\n            return true;\n        }'''
new='''    fn spine_probe(&mut self, depth: u32, sx: S<'t>, sy: S<'t>, sig: Sig, limit: u32) -> bool {\n        MG_SPINE_PROBE.fetch_add(1, Ordering::Relaxed);\n        if std::ptr::eq(sx, sy) {\n            MG_SPINE_PROBE_TRUE.fetch_add(1, Ordering::Relaxed);\n            return true;\n        }'''
assert old in s; s=s.replace(old,new,1)
old='''        let decided = self.probe_pass(depth, &pairs);\n        self.tc_cache.probe_exhausted = outer;\n        decided'''
new='''        let decided = self.probe_pass(depth, &pairs);\n        self.tc_cache.probe_exhausted = outer;\n        if decided { MG_SPINE_PROBE_TRUE.fetch_add(1, Ordering::Relaxed); }\n        decided'''
assert old in s; s=s.replace(old,new,1)

old='''    fn try_proof_irrel_at(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {'''
new='''    fn try_proof_irrel_at(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {\n        MG_PROOF_IRREL.fetch_add(1, Ordering::Relaxed);'''
assert old in s; s=s.replace(old,new,1)
# Count successes at direct return sites by wrapping public call is invasive; count the common positive result below instead.
old='''        if !self.is_prop_type(depth, tx) {\n            return false;\n        }'''
new='''        if !self.is_prop_type(depth, tx) {\n            return false;\n        }\n        MG_PROOF_IRREL_TRUE.fetch_add(1, Ordering::Relaxed);'''
assert old in s; s=s.replace(old,new,1)

old='''    fn unify_iota<const RIGID: bool>(\n'''
new='''    fn unify_iota<const RIGID: bool>(\n'''
assert old in s
# increment after signature closes using unique body line
old2='''        let (sig, limit) = if heads_match { self.head_spine_sig(name, levels, sx, sy) } else { (Sig::ALL_RELEVANT, 0) };'''
new2='''        MG_IOTA_PAIR.fetch_add(1, Ordering::Relaxed);\n        let (sig, limit) = if heads_match { self.head_spine_sig(name, levels, sx, sy) } else { (Sig::ALL_RELEVANT, 0) };'''
assert old2 in s; s=s.replace(old2,new2,1)

old='''    fn try_struct_eta(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {'''
new='''    fn try_struct_eta(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {\n        MG_STRUCT_ETA.fetch_add(1, Ordering::Relaxed);'''
assert old in s; s=s.replace(old,new,1)
p.write_text(s)

p=Path('/tmp/v2/src/main.rs'); s=p.read_text()
old='''    // Pretty print as necessary\n    let pp_errs = export_file.pp_selected_declars(pp_destination.as_mut());'''
new='''    sokonanoda::conv::report_conversion_choice_census();\n    // Pretty print as necessary\n    let pp_errs = export_file.pp_selected_declars(pp_destination.as_mut());'''
assert old in s; p.write_text(s.replace(old,new,1))
PY

cd /tmp/v2
cargo test --release --locked
RUSTFLAGS='-C target-cpu=x86-64' cargo build --release --locked
cp target/release/sokonanoda /tmp/v2-conv-census
cat >/tmp/checker.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/arena
cd /tmp/arena
for t in init std mathlib; do nix develop -c ./lka.py build-test "$t"; done
: >/tmp/conv-census.txt
for t in init std mathlib; do
  echo "MG_TEST $t" | tee -a /tmp/conv-census.txt
  MATHGRAPH_CONV_CENSUS=1 /tmp/v2-conv-census /tmp/checker.json < "_build/tests/$t.ndjson" >/tmp/$t.out 2>/tmp/$t.err
  grep '^MG_CONV' /tmp/$t.err | tee -a /tmp/conv-census.txt
done
python3 - <<'PY' | tee /tmp/conv-decision.txt
import re
from pathlib import Path
rows={}; cur=None
for line in Path('/tmp/conv-census.txt').read_text().splitlines():
    if line.startswith('MG_TEST '): cur=line.split()[1]; rows[cur]={}
    elif line.startswith('MG_CONV') and cur:
        rows[cur].update({k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)})
for t,r in rows.items():
    u=r.get('unify',0); uu=r.get('uu',0); mm=r.get('uu_head_mismatch',0); os=r.get('one_sided_unfold',0)
    print(f"{t}: unify={u:,} ptr_eq={r.get('ptr_eq',0):,} cache_pos={r.get('cache_pos',0):,} cache_neg={r.get('cache_neg',0):,} unfold/unfold={uu:,} mismatched_heads={mm:,} one_sided={os:,} hint_left={r.get('hint_left',0):,} hint_right={r.get('hint_right',0):,} hint_equal={r.get('hint_equal',0):,} spine_probe={r.get('spine_probe',0):,} spine_probe_true={r.get('spine_probe_true',0):,} proof_irrel={r.get('proof_irrel',0):,} proof_irrel_true={r.get('proof_irrel_true',0):,} iota_pair={r.get('iota_pair',0):,}")
m=rows.get('mathlib',{})
choice=m.get('uu_head_mismatch',0)+m.get('one_sided_unfold',0)
print('MATHLIB_CHOICE_EVENTS='+str(choice))
print('DECISION=' + ('BUILD_ADAPTIVE_CONVERSION_SCHEDULER' if choice >= 10_000_000 else 'CONVERSION_CHOICE_TOO_SPARSE'))
PY
cp /tmp/conv-census.txt /tmp/conv-decision.txt "$GITHUB_WORKSPACE"/ || true
