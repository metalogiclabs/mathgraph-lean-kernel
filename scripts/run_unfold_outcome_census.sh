#!/usr/bin/env bash
set -euo pipefail
V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
ROOT=$(pwd)
rm -rf /tmp/mg-outcome-census /tmp/arena-outcome

git worktree add /tmp/mg-outcome-census "$V2"
cd /tmp/mg-outcome-census
python3 - <<'PY'
from pathlib import Path
p=Path('src/conv.rs')
s=p.read_text()
insert='''\nuse std::sync::atomic::{AtomicU64, Ordering};\nstatic UF_PAIR_CALLS: AtomicU64 = AtomicU64::new(0);\nstatic UF_LEFT_ONLY: AtomicU64 = AtomicU64::new(0);\nstatic UF_RIGHT_ONLY: AtomicU64 = AtomicU64::new(0);\nstatic UF_BOTH_PROGRESS: AtomicU64 = AtomicU64::new(0);\nstatic UF_NEITHER_PROGRESS: AtomicU64 = AtomicU64::new(0);\nstatic UF_LEFT_CTOR: AtomicU64 = AtomicU64::new(0);\nstatic UF_RIGHT_CTOR: AtomicU64 = AtomicU64::new(0);\nstatic UF_LEFT_RECURSOR: AtomicU64 = AtomicU64::new(0);\nstatic UF_RIGHT_RECURSOR: AtomicU64 = AtomicU64::new(0);\nstatic UF_LEFT_LAM: AtomicU64 = AtomicU64::new(0);\nstatic UF_RIGHT_LAM: AtomicU64 = AtomicU64::new(0);\nstatic UF_LEFT_PI: AtomicU64 = AtomicU64::new(0);\nstatic UF_RIGHT_PI: AtomicU64 = AtomicU64::new(0);\nstatic UF_LEFT_UNFOLD: AtomicU64 = AtomicU64::new(0);\nstatic UF_RIGHT_UNFOLD: AtomicU64 = AtomicU64::new(0);\nstatic UF_PTR_EQUAL_AFTER: AtomicU64 = AtomicU64::new(0);\n\npub fn dump_unfold_outcome_census() {\n    macro_rules! p { ($n:literal,$x:ident) => { eprintln!(concat!(\"MG_CENSUS \",$n,\"={}\"), $x.load(Ordering::Relaxed)); }; }\n    p!(\"pair_calls\",UF_PAIR_CALLS); p!(\"left_only\",UF_LEFT_ONLY); p!(\"right_only\",UF_RIGHT_ONLY);\n    p!(\"both_progress\",UF_BOTH_PROGRESS); p!(\"neither_progress\",UF_NEITHER_PROGRESS);\n    p!(\"left_ctor\",UF_LEFT_CTOR); p!(\"right_ctor\",UF_RIGHT_CTOR);\n    p!(\"left_recursor\",UF_LEFT_RECURSOR); p!(\"right_recursor\",UF_RIGHT_RECURSOR);\n    p!(\"left_lam\",UF_LEFT_LAM); p!(\"right_lam\",UF_RIGHT_LAM); p!(\"left_pi\",UF_LEFT_PI); p!(\"right_pi\",UF_RIGHT_PI);\n    p!(\"left_unfold\",UF_LEFT_UNFOLD); p!(\"right_unfold\",UF_RIGHT_UNFOLD); p!(\"ptr_equal_after\",UF_PTR_EQUAL_AFTER);\n}\n'''
s=s.replace('use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};', 'use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};'+insert)
old='''    fn unfold_pair(&mut self, depth: u32, t: V<'t>, t2: V<'t>) -> bool {\n        let v1 = self.unfold_value(depth, t);\n        let v2 = self.unfold_value(depth, t2);\n'''
new='''    fn unfold_pair(&mut self, depth: u32, t: V<'t>, t2: V<'t>) -> bool {\n        UF_PAIR_CALLS.fetch_add(1, Ordering::Relaxed);\n        let v1 = self.unfold_value(depth, t);\n        let v2 = self.unfold_value(depth, t2);\n        let lp = !std::ptr::eq(v1, t); let rp = !std::ptr::eq(v2, t2);\n        match (lp,rp) { (true,false)=>{UF_LEFT_ONLY.fetch_add(1,Ordering::Relaxed);}, (false,true)=>{UF_RIGHT_ONLY.fetch_add(1,Ordering::Relaxed);}, (true,true)=>{UF_BOTH_PROGRESS.fetch_add(1,Ordering::Relaxed);}, (false,false)=>{UF_NEITHER_PROGRESS.fetch_add(1,Ordering::Relaxed);} }\n        if std::ptr::eq(v1,v2) { UF_PTR_EQUAL_AFTER.fetch_add(1,Ordering::Relaxed); }\n        match v1 { Value::Rigid { head: RigidHead::Ctor(..), .. } => {UF_LEFT_CTOR.fetch_add(1,Ordering::Relaxed);}, Value::Rigid { head: RigidHead::Recursor(..)|RigidHead::QuotConst(..), .. } => {UF_LEFT_RECURSOR.fetch_add(1,Ordering::Relaxed);}, Value::Lam{..}=>{UF_LEFT_LAM.fetch_add(1,Ordering::Relaxed);}, Value::Pi{..}=>{UF_LEFT_PI.fetch_add(1,Ordering::Relaxed);}, Value::Unfold{..}=>{UF_LEFT_UNFOLD.fetch_add(1,Ordering::Relaxed);}, _=>{} }\n        match v2 { Value::Rigid { head: RigidHead::Ctor(..), .. } => {UF_RIGHT_CTOR.fetch_add(1,Ordering::Relaxed);}, Value::Rigid { head: RigidHead::Recursor(..)|RigidHead::QuotConst(..), .. } => {UF_RIGHT_RECURSOR.fetch_add(1,Ordering::Relaxed);}, Value::Lam{..}=>{UF_RIGHT_LAM.fetch_add(1,Ordering::Relaxed);}, Value::Pi{..}=>{UF_RIGHT_PI.fetch_add(1,Ordering::Relaxed);}, Value::Unfold{..}=>{UF_RIGHT_UNFOLD.fetch_add(1,Ordering::Relaxed);}, _=>{} }\n'''
if old not in s: raise SystemExit('unfold_pair anchor not found')
s=s.replace(old,new)
p.write_text(s)

m=Path('src/main.rs'); x=m.read_text()
x=x.replace('    match out {', '    sokonanoda::conv::dump_unfold_outcome_census();\n    match out {')
m.write_text(x)
PY
cargo test --release --locked
RUSTFLAGS='-C target-cpu=x86-64' cargo build --release --locked
cp target/release/sokonanoda /tmp/mg-outcome-census-bin

cd /tmp
git clone --depth 1 https://github.com/leanprover/lean-kernel-arena arena-outcome
cd arena-outcome
nix develop -c ./lka.py build-test init-prelude
nix develop -c ./lka.py build-test mathlib
cat > /tmp/checker.json <<'EOF'
{
  "use_stdin": true,
  "nat_extension": true,
  "string_extension": true,
  "unpermitted_axiom_hard_error": false,
  "unsafe_permit_all_axioms": true,
  "num_threads": 4
}
EOF
# Preflight the exact Arena invocation shape before spending a Mathlib run.
set +e
/tmp/mg-outcome-census-bin /tmp/checker.json < /tmp/arena-outcome/_build/tests/init-prelude.ndjson >/dev/null 2>/tmp/preflight.stderr
PRE_STATUS=$?
set -e
echo "PREFLIGHT_STATUS=$PRE_STATUS"
if [ "$PRE_STATUS" -ne 0 ]; then
  cat /tmp/preflight.stderr
  exit 1
fi

set +e
/usr/bin/time -f 'WALL_SECONDS=%e' /tmp/mg-outcome-census-bin /tmp/checker.json < /tmp/arena-outcome/_build/tests/mathlib.ndjson >/dev/null 2> /tmp/outcome-census.stderr
CHECKER_STATUS=$?
set -e
{
  echo "CHECKER_STATUS=$CHECKER_STATUS"
  grep -E 'MG_CENSUS|WALL_SECONDS|Command exited' /tmp/outcome-census.stderr || true
} | tee "$ROOT/unfold-outcome-census.txt"
# A valid census must actually process unfold pairs; zero means launch/instrumentation failure.
PAIR_CALLS=$(sed -n 's/.*MG_CENSUS pair_calls=//p' "$ROOT/unfold-outcome-census.txt" | tail -1)
[ -n "$PAIR_CALLS" ]
[ "$PAIR_CALLS" -gt 0 ]
