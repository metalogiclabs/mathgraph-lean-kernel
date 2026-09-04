#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v51-* /tmp/v51-arena
for arm in base prop_off; do git worktree add "/tmp/v51-$arm" "$BASE"; done

# Verified Pi-only incumbent in both arms.
for d in /tmp/v51-base /tmp/v51-prop_off; do
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

# v48 survivor only: preserve argument-domain relevance and terminal result classification;
# remove only backward per-binder imax/result propagation. Unknown remains conservative.
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v51-prop_off/src/relevance.rs'); s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
new='''                let _ = r;'''
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY

cat >/tmp/v51-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

for arm in base prop_off; do
  (cd "/tmp/v51-$arm" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
  cp "/tmp/v51-$arm/target/release/sokonanoda" "/tmp/v51-$arm-bin"
done

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v51-arena
cd /tmp/v51-arena
nix develop -c ./lka.py build-test mathlib

/tmp/v51-base-bin /tmp/v51-config.json < _build/tests/mathlib.ndjson >/tmp/v51-mathlib-base.out 2>/tmp/v51-mathlib-base.err
/tmp/v51-prop_off-bin /tmp/v51-config.json < _build/tests/mathlib.ndjson >/tmp/v51-mathlib-prop_off.out 2>/tmp/v51-mathlib-prop_off.err
cmp /tmp/v51-mathlib-base.out /tmp/v51-mathlib-prop_off.out
echo 'V51_MATHLIB_SEMANTIC_REPLAY=EXACT'

rm -f /tmp/v51-*.time
orders=("base prop_off" "prop_off base" "base prop_off" "prop_off base")
r=0
for order in "${orders[@]}"; do
  r=$((r+1))
  for arm in $order; do
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v51-${arm}-${r}.time" \
      "/tmp/v51-$arm-bin" /tmp/v51-config.json < _build/tests/mathlib.ndjson >/dev/null 2>"/tmp/v51-${arm}-${r}.err"
  done
done

python3 - <<'PY' | tee /tmp/v51-decision.txt
from pathlib import Path
from statistics import median
vals={}
for a in ('base','prop_off'):
    xs=[float(p.read_text().split()[0]) for p in sorted(Path('/tmp').glob(f'v51-{a}-*.time'))]
    assert len(xs)==4,(a,xs)
    vals[a]=median(xs)
    print(f'V51_TIMES {a} raw={xs} median={vals[a]:.3f}')
d=(vals['prop_off']/vals['base']-1)*100
print(f'V51_MATHLIB_DELTA={d:+.4f}%')
if d <= -2.0:
    print('DECISION=V51_MATERIAL_TRANSFER_WIN__RETAIN_PROPAGATION_OFF_ON_PI')
elif d < 0:
    print('DECISION=V51_WEAK_TRANSFER_WIN__RETAIN_AS_NONINCUMBENT_AND_TEST_INTERACTION')
else:
    print('DECISION=V51_KILL_PROPAGATION_OFF__RESULT_PROPAGATION_IS_CONSEQUENTIAL_AT_MATHLIB_SCALE')
print('RULE=ACT_VERIFY_RETAIN_ONLY_TRANSFERRED_CONSEQUENTIAL_DISTINCTIONS')
PY
