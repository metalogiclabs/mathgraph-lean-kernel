#!/usr/bin/env bash
set -euxo pipefail
SOKO=7b51784fe4ec9b82bf7a20c71ba6bf803a4ed7c0
ROOT=/tmp/v65
rm -rf "$ROOT" && mkdir -p "$ROOT"

git clone https://github.com/intgrah/sokonanoda "$ROOT/incumbent"
git -C "$ROOT/incumbent" checkout "$SOKO"

python3 - "$ROOT/incumbent" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/'src/eval.rs'; s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
p=root/'src/relevance.rs'; s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
assert s.count(old)==1
p.write_text(s.replace(old,'                let _ = r;',1))
PY

python3 - "$ROOT/incumbent" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/'src/eval.rs'; s=p.read_text()
anchor='use std::collections::hash_map::Entry;\n'
insert='''use std::collections::hash_map::Entry;\nuse std::sync::atomic::{AtomicU64, Ordering::Relaxed};\n\nstatic MISS_TOTAL: AtomicU64 = AtomicU64::new(0);\nstatic MISS_APP: AtomicU64 = AtomicU64::new(0);\nstatic MISS_PROJ: AtomicU64 = AtomicU64::new(0);\nstatic MISS_LET: AtomicU64 = AtomicU64::new(0);\nstatic MISS_PI: AtomicU64 = AtomicU64::new(0);\nstatic MISS_LAM: AtomicU64 = AtomicU64::new(0);\nstatic MISS_DEP0: AtomicU64 = AtomicU64::new(0);\nstatic MISS_DEP1: AtomicU64 = AtomicU64::new(0);\nstatic MISS_DEP2: AtomicU64 = AtomicU64::new(0);\nstatic MISS_DEP3_4: AtomicU64 = AtomicU64::new(0);\nstatic MISS_DEP5_8: AtomicU64 = AtomicU64::new(0);\nstatic MISS_DEP9P: AtomicU64 = AtomicU64::new(0);\nstatic MISS_APP_DEP1: AtomicU64 = AtomicU64::new(0);\nstatic MISS_PI_DEP1: AtomicU64 = AtomicU64::new(0);\nstatic MISS_LAM_DEP1: AtomicU64 = AtomicU64::new(0);\n\npub fn dump_open_miss_census() {\n    let total=MISS_TOTAL.load(Relaxed).max(1);\n    macro_rules! out { ($n:literal,$c:ident) => {{ let v=$c.load(Relaxed); eprintln!(\"V65_{}={} SHARE_PCT={:.6}\",$n,v,100.0*(v as f64)/(total as f64)); }} }\n    eprintln!(\"V65_OPEN_MISS_TOTAL={}\", total);\n    out!(\"MISS_APP\",MISS_APP); out!(\"MISS_PROJ\",MISS_PROJ); out!(\"MISS_LET\",MISS_LET); out!(\"MISS_PI\",MISS_PI); out!(\"MISS_LAM\",MISS_LAM);\n    out!(\"MISS_DEP0\",MISS_DEP0); out!(\"MISS_DEP1\",MISS_DEP1); out!(\"MISS_DEP2\",MISS_DEP2); out!(\"MISS_DEP3_4\",MISS_DEP3_4); out!(\"MISS_DEP5_8\",MISS_DEP5_8); out!(\"MISS_DEP9P\",MISS_DEP9P);\n    out!(\"MISS_APP_DEP1\",MISS_APP_DEP1); out!(\"MISS_PI_DEP1\",MISS_PI_DEP1); out!(\"MISS_LAM_DEP1\",MISS_LAM_DEP1);\n}\n'''
assert s.count(anchor)==1
s=s.replace(anchor,insert,1)
old='''            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {\n                return v;\n            }\n            let v = self.eval_no_cache(depth, te, e);'''
new='''            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {\n                return v;\n            }\n            MISS_TOTAL.fetch_add(1, Relaxed);\n            let dep = if e.num_loose_bvars() <= 64 { e.as_ref().fv_mask().count_ones() } else { 65 };\n            match dep { 0 => { MISS_DEP0.fetch_add(1,Relaxed); }, 1 => { MISS_DEP1.fetch_add(1,Relaxed); }, 2 => { MISS_DEP2.fetch_add(1,Relaxed); }, 3|4 => { MISS_DEP3_4.fetch_add(1,Relaxed); }, 5..=8 => { MISS_DEP5_8.fetch_add(1,Relaxed); }, _ => { MISS_DEP9P.fetch_add(1,Relaxed); } }\n            match self.ctx.read_expr_ref(e) {\n                Expr::App { .. } => { MISS_APP.fetch_add(1,Relaxed); if dep==1 { MISS_APP_DEP1.fetch_add(1,Relaxed); } },\n                Expr::Proj { .. } => { MISS_PROJ.fetch_add(1,Relaxed); },\n                Expr::Let { .. } => { MISS_LET.fetch_add(1,Relaxed); },\n                Expr::Pi { .. } => { MISS_PI.fetch_add(1,Relaxed); if dep==1 { MISS_PI_DEP1.fetch_add(1,Relaxed); } },\n                Expr::Lambda { .. } => { MISS_LAM.fetch_add(1,Relaxed); if dep==1 { MISS_LAM_DEP1.fetch_add(1,Relaxed); } },\n                _ => {}\n            }\n            let v = self.eval_no_cache(depth, te, e);'''
assert s.count(old)==1
s=s.replace(old,new,1)
p.write_text(s)
p=root/'src/main.rs'; s=p.read_text()
old='''    // Check the environment\n    export_file.check_all_declars();\n    // Pretty print as necessary'''
new='''    // Check the environment\n    export_file.check_all_declars();\n    sokonanoda::eval::dump_open_miss_census();\n    // Pretty print as necessary'''
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
ARENA=$(git -C "$ROOT/arena" rev-parse HEAD); echo "V65_ARENA_HEAD=$ARENA"
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t"; done
cd "$ROOT/incumbent"
RUSTFLAGS='-C target-cpu=native' cargo build --release --locked
mkdir -p "$ROOT/out"
for t in std cedar mathlib; do
  ./target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" >"$ROOT/out/$t.out" 2>"$ROOT/out/$t.census"
  echo "V65_${t^^}_CHECK=PASS"
  grep '^V65_' "$ROOT/out/$t.census" | sed "s/^/V65_${t^^}_/" | tee "$ROOT/out/$t.summary"
done
python3 - <<'PY' | tee "$ROOT/decision.txt"
from pathlib import Path
import re
for t in ('std','cedar','mathlib'):
    txt=Path(f'/tmp/v65/out/{t}.summary').read_text()
    vals={m.group(1):float(m.group(2)) for m in re.finditer(r'V65_[A-Z]+_V65_([A-Z0-9_]+)=\d+ SHARE_PCT=([0-9.]+)',txt)}
    kinds=sorted(((k,v) for k,v in vals.items() if k in {'MISS_APP','MISS_PROJ','MISS_LET','MISS_PI','MISS_LAM'}),key=lambda x:-x[1])
    deps=sorted(((k,v) for k,v in vals.items() if k.startswith('MISS_DEP')),key=lambda x:-x[1])
    print(f'V65_{t.upper()}_KIND_SHARES={kinds}')
    print(f'V65_{t.upper()}_DEP_SHARES={deps}')
print('DECISION=V65_OPEN_MISS_SHAPE_CENSUS_COMPLETE__SELECT_LARGEST_LOW_DEPENDENCY_CLASS_FOR_BYPASS')
print('RULE=DO_NOT_ADD_ANOTHER_PREHIT_CACHE__BYPASS_ONLY_A_MEASURED_LOW_REUSE_CLASS')
PY
