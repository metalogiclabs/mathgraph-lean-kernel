#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v47-* /tmp/v47-arena

for arm in base arg; do git worktree add "/tmp/v47-$arm" "$BASE"; done

# Pi-only verified incumbent in both arms.
for d in /tmp/v47-base /tmp/v47-arg; do
python3 - "$d" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/eval.rs'; s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY
done

# Exact v46 ARG-OFF candidate: retain telescope traversal and typed fresh BVars,
# but do not compute binder-domain level relevance. Unknown => conservatively relevant.
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v47-arg/src/relevance.rs'); s=p.read_text()
old='''            let d = *domain;\n            dom.push(self.level_of_type(depth, d));\n            let fresh = self.mk_bvar_hc(depth, d);'''
new='''            let d = *domain;\n            dom.push(None);\n            let fresh = self.mk_bvar_hc(depth, d);'''
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY

cat >/tmp/v47-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

for arm in base arg; do
  (cd "/tmp/v47-$arm" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
  cp "/tmp/v47-$arm/target/release/sokonanoda" "/tmp/v47-$arm-bin"
done

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v47-arena
cd /tmp/v47-arena
nix develop -c ./lka.py build-test mathlib

/tmp/v47-base-bin /tmp/v47-config.json < _build/tests/mathlib.ndjson >/tmp/v47-mathlib-base.out 2>/tmp/v47-mathlib-base.err
/tmp/v47-arg-bin /tmp/v47-config.json < _build/tests/mathlib.ndjson >/tmp/v47-mathlib-arg.out 2>/tmp/v47-mathlib-arg.err
cmp /tmp/v47-mathlib-base.out /tmp/v47-mathlib-arg.out
echo 'V47_MATHLIB_SEMANTIC_REPLAY=EXACT'

rm -f /tmp/v47-*.time
orders=("base arg" "arg base" "base arg" "arg base")
r=0
for order in "${orders[@]}"; do
  r=$((r+1))
  for arm in $order; do
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v47-${arm}-${r}.time" \
      "/tmp/v47-$arm-bin" /tmp/v47-config.json < _build/tests/mathlib.ndjson >/dev/null 2>"/tmp/v47-${arm}-${r}.err"
  done
done

python3 - <<'PY' | tee /tmp/v47-decision.txt
from pathlib import Path
from statistics import median
vals={}
for a in ('base','arg'):
    xs=[float(p.read_text().split()[0]) for p in sorted(Path('/tmp').glob(f'v47-{a}-*.time'))]
    assert len(xs)==4,(a,xs)
    vals[a]=median(xs)
    print(f'V47_TIMES {a} raw={xs} median={vals[a]:.3f}')
d=(vals['arg']/vals['base']-1)*100
print(f'V47_MATHLIB_DELTA={d:+.4f}%')
if d <= -2:
    print('DECISION=V47_MATERIAL_MATHLIB_WIN__ARG_LEVEL_RELEVANCE_IS_NET_TAX__PROMOTE_AND_SIMPLIFY')
elif d < 0:
    print('DECISION=V47_WEAK_MATHLIB_WIN__RETAIN_ARG_OFF_AND_TEST_INTERACTION')
else:
    print('DECISION=V47_KILL_ARG_OFF__LOCAL_GAIN_DID_NOT_TRANSFER__SHARED_TRAVERSAL_REMAINS')
print('RULE=ACT_VERIFY_RETAIN_ONLY_TRANSFERRED_CONSEQUENTIAL_DISTINCTIONS')
PY
