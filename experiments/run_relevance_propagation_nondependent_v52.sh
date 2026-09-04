#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v52-* /tmp/v52-arena
for arm in base prop_off combo; do git worktree add "/tmp/v52-$arm" "$BASE"; done

# Verified Pi-only incumbent in every arm.
for d in /tmp/v52-base /tmp/v52-prop_off /tmp/v52-combo; do
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

# v51 retained change: remove only backward result propagation.
for d in /tmp/v52-prop_off /tmp/v52-combo; do
python3 - "$d" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/relevance.rs'; s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
assert s.count(old)==1
p.write_text(s.replace(old,'                let _ = r;',1))
PY
done

# v52 candidate: preserve argument-domain level classification, but when the
# closure body is structurally nondependent, evaluate it without allocating/
# applying a fresh semantic BVar. This is the isolated form of the v50 idea.
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v52-combo/src/relevance.rs'); s=p.read_text()
old='''            let d = *domain;\n            dom.push(self.level_of_type(depth, d));\n            let fresh = self.mk_bvar_hc(depth, d);\n            cur = self.apply_closure(depth + 1, body, fresh, Some(d));\n            depth += 1;'''
new='''            let d = *domain;\n            dom.push(self.level_of_type(depth, d));\n            if body.ctx.is_none() && self.ctx.num_loose_bvars(body.body) == 0 {\n                cur = self.eval(depth, body.env, body.body);\n            } else {\n                let fresh = self.mk_bvar_hc(depth, d);\n                cur = self.apply_closure(depth + 1, body, fresh, Some(d));\n            }\n            depth += 1;'''
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY

cat >/tmp/v52-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

for arm in base prop_off combo; do
  (cd "/tmp/v52-$arm" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
  cp "/tmp/v52-$arm/target/release/sokonanoda" "/tmp/v52-$arm-bin"
done

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v52-arena
cd /tmp/v52-arena
nix develop -c ./lka.py build-test mathlib

for arm in base prop_off combo; do
  /tmp/v52-$arm-bin /tmp/v52-config.json < _build/tests/mathlib.ndjson >"/tmp/v52-mathlib-$arm.out" 2>"/tmp/v52-mathlib-$arm.err"
done
cmp /tmp/v52-mathlib-base.out /tmp/v52-mathlib-prop_off.out
cmp /tmp/v52-mathlib-base.out /tmp/v52-mathlib-combo.out
echo 'V52_MATHLIB_SEMANTIC_REPLAY=EXACT'

rm -f /tmp/v52-*.time
orders=("base prop_off combo" "combo prop_off base" "prop_off base combo")
r=0
for order in "${orders[@]}"; do
  r=$((r+1))
  for arm in $order; do
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v52-${arm}-${r}.time" \
      "/tmp/v52-$arm-bin" /tmp/v52-config.json < _build/tests/mathlib.ndjson >/dev/null 2>"/tmp/v52-${arm}-${r}.err"
  done
done

python3 - <<'PY' | tee /tmp/v52-decision.txt
from pathlib import Path
from statistics import median
vals={}
for a in ('base','prop_off','combo'):
    xs=[float(p.read_text().split()[0]) for p in sorted(Path('/tmp').glob(f'v52-{a}-*.time'))]
    assert len(xs)==3,(a,xs)
    vals[a]=median(xs)
    print(f'V52_TIMES {a} raw={xs} median={vals[a]:.3f}')
for a,b,label in [('base','prop_off','PROP_OFF_VS_BASE'),('prop_off','combo','BYPASS_INCREMENTAL'),('base','combo','COMBO_VS_BASE')]:
    d=(vals[b]/vals[a]-1)*100
    print(f'V52_{label}_DELTA={d:+.4f}%')
inc=(vals['combo']/vals['prop_off']-1)*100
if inc <= -2.0:
    print('DECISION=V52_BYPASS_MATERIAL_ON_V51__PROMOTE_COMPOUND')
elif inc < 0:
    print('DECISION=V52_BYPASS_WEAK_ON_V51__RETAIN_ONLY_IF_REPEATABLE')
else:
    print('DECISION=V52_BYPASS_KILL__NONDEPENDENT_SHORTCUT_NOT_ADDITIVE')
print('RULE=TEST_CANDIDATE_INTERACTIONS_ON_CURRENT_VERIFIED_INCUMBENT')
PY
