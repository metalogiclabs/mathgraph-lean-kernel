#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
ARMS=(base same1)
rm -rf /tmp/v36-* /tmp/v36-arena

for arm in "${ARMS[@]}"; do
  git worktree add "/tmp/v36-$arm" "$BASE"
  python3 - "$arm" <<'PY'
from pathlib import Path
import sys
arm=sys.argv[1]
# Verified v29 wall-time seed: Pi-only force collapse in both arms.
p=Path(f'/tmp/v36-{arm}/src/eval.rs'); s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {
        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {
        if matches!(v, Value::Pi { .. }) { return v; }
        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
if arm == 'base': raise SystemExit

# Exact v35 winning same1 patch, unchanged.
p=Path(f'/tmp/v36-{arm}/src/conv.rs'); s=p.read_text()
old=r'''    fn unfold_pair(&mut self, depth: u32, t: V<'t>, t2: V<'t>) -> bool {
        let v1 = self.unfold_value(depth, t);
        let v2 = self.unfold_value(depth, t2);
        if std::ptr::eq(v1, t) && std::ptr::eq(v2, t2) {
            let f1 = self.unfold_value_demand(depth, t);
            let f2 = self.unfold_value_demand(depth, t2);
            if std::ptr::eq(f1, t) && std::ptr::eq(f2, t2) {
                return false;
            }
            return self.unify::<true>(depth, f1, f2);
        }
        self.unify::<true>(depth, v1, v2)
    }'''
assert s.count(old)==1
new=r'''    fn unfold_pair(&mut self, depth: u32, t: V<'t>, t2: V<'t>) -> bool {
        let mut a = t;
        let mut b = t2;
        let mut fused = 0u32;
        loop {
            let v1 = self.unfold_value(depth, a);
            let v2 = self.unfold_value(depth, b);
            if std::ptr::eq(v1, a) && std::ptr::eq(v2, b) {
                let f1 = self.unfold_value_demand(depth, a);
                let f2 = self.unfold_value_demand(depth, b);
                if std::ptr::eq(f1, a) && std::ptr::eq(f2, b) { return false; }
                return self.unify::<true>(depth, f1, f2);
            }
            if std::ptr::eq(v1, v2) { return true; }
            if fused >= 1 { return self.unify::<true>(depth, v1, v2); }
            match (v1, v2) {
                (
                    Value::Unfold { head: UnfoldHead { name: nx, levels: lx }, spine: sx, .. },
                    Value::Unfold { head: UnfoldHead { name: ny, levels: ly }, spine: sy, .. },
                ) if nx == ny && self.ctx.eq_antisymm_many(*lx, *ly) => {
                    let nx = *nx;
                    let lx = *lx;
                    let sx = *sx;
                    let sy = *sy;
                    let (sig, lim) = self.head_spine_sig(nx, lx, sx, sy);
                    if self.spine_probe(depth, sx, sy, sig, lim) { return true; }
                    if self.try_proof_irrel_at(depth, v1, v2) { return true; }
                    a = v1; b = v2; fused += 1;
                }
                _ => return self.unify::<true>(depth, v1, v2),
            }
        }
    }'''
p.write_text(s.replace(old,new,1))
PY
done

cat >/tmp/v36-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

for arm in "${ARMS[@]}"; do
  (cd "/tmp/v36-$arm" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
  cp "/tmp/v36-$arm/target/release/sokonanoda" "/tmp/v36-$arm-bin"
done

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v36-arena
cd /tmp/v36-arena
nix develop -c ./lka.py build-test mathlib

# Full Mathlib semantic differential before timing.
/tmp/v36-base-bin /tmp/v36-config.json < _build/tests/mathlib.ndjson >/tmp/v36-mathlib-base.out 2>/tmp/v36-mathlib-base.err
/tmp/v36-same1-bin /tmp/v36-config.json < _build/tests/mathlib.ndjson >/tmp/v36-mathlib-same1.out 2>/tmp/v36-mathlib-same1.err
cmp /tmp/v36-mathlib-base.out /tmp/v36-mathlib-same1.out
echo 'V36_MATHLIB_SEMANTIC_REPLAY=EXACT'

# Four balanced alternating wall rounds; candidate occupies each order position twice.
rm -f /tmp/v36-*.time
orders=("base same1" "same1 base" "base same1" "same1 base")
r=0
for order in "${orders[@]}"; do
  r=$((r+1))
  for arm in $order; do
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v36-${arm}-${r}.time" \
      "/tmp/v36-$arm-bin" /tmp/v36-config.json < _build/tests/mathlib.ndjson >/dev/null 2>"/tmp/v36-${arm}-${r}.err"
  done
done

python3 - <<'PY' | tee /tmp/v36-decision.txt
from pathlib import Path
from statistics import median
vals={}
for a in ['base','same1']:
    xs=[float(p.read_text().split()[0]) for p in sorted(Path('/tmp').glob(f'v36-{a}-*.time'))]
    assert len(xs)==4,(a,xs)
    vals[a]=median(xs)
    print(f'V36_TIMES {a} raw={xs} median={vals[a]:.3f}')
d=(vals['same1']/vals['base']-1.0)*100
print(f'V36_MATHLIB_DELTA={d:+.4f}%')
if d <= -2.0:
    print('DECISION=V36_MATERIAL_MATHLIB_WIN__PROMOTE_SAME1_ON_PI_SEED')
elif d < 0:
    print('DECISION=V36_WEAK_MATHLIB_WIN__RETAIN_NOT_INCUMBENT')
else:
    print('DECISION=V36_KILL_SAME1__LOCAL_REENTRY_FUSION_DOES_NOT_TRANSFER_TO_MATHLIB')
print('V36_NEXT_IF_NOT_MATERIAL=route to unequal-hint/value-domain continuation representation; do not increase same-head loop depth')
PY
