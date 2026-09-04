#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v49-* /tmp/v49-arena
for arm in base minimal; do git worktree add "/tmp/v49-$arm" "$BASE"; done

# Pi-only verified incumbent in both arms.
for d in /tmp/v49-base /tmp/v49-minimal; do
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

# Minimal relevance core licensed by v46+v48:
# - keep typed telescope traversal and fresh binders
# - drop argument-domain level classification (unknown => relevant)
# - keep terminal result classification
# - drop backward per-binder result propagation (unknown => no shortcut)
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v49-minimal/src/relevance.rs'); s=p.read_text()
old='''            let d = *domain;\n            dom.push(self.level_of_type(depth, d));\n            let fresh = self.mk_bvar_hc(depth, d);'''
new='''            let d = *domain;\n            dom.push(None);\n            let fresh = self.mk_bvar_hc(depth, d);'''
assert s.count(old)==1
s=s.replace(old,new,1)
old2='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
new2='''                let _ = r;'''
assert s.count(old2)==1
p.write_text(s.replace(old2,new2,1))
PY

cat >/tmp/v49-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v49-arena
(cd /tmp/v49-arena && for t in std cedar; do nix develop -c ./lka.py build-test "$t"; done)

for arm in base minimal; do
  (cd "/tmp/v49-$arm" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
  cp "/tmp/v49-$arm/target/release/sokonanoda" "/tmp/v49-$arm-bin"
done

for t in std cedar; do
  /tmp/v49-base-bin /tmp/v49-config.json < "/tmp/v49-arena/_build/tests/$t.ndjson" >"/tmp/v49-$t-base.out" 2>"/tmp/v49-$t-base.err"
  /tmp/v49-minimal-bin /tmp/v49-config.json < "/tmp/v49-arena/_build/tests/$t.ndjson" >"/tmp/v49-$t-minimal.out" 2>"/tmp/v49-$t-minimal.err"
  cmp "/tmp/v49-$t-base.out" "/tmp/v49-$t-minimal.out"
  echo "V49_${t^^}_SEMANTIC_REPLAY=EXACT"
  for arm in base minimal minimal base; do
    n=$(find /tmp -maxdepth 1 -type f -name "v49-${t}-${arm}-*.time" | wc -l); n=$((n+1))
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v49-${t}-${arm}-${n}.time" "/tmp/v49-$arm-bin" /tmp/v49-config.json < "/tmp/v49-arena/_build/tests/$t.ndjson" >/dev/null 2>"/tmp/v49-${t}-${arm}-${n}.err"
  done
done

python3 - <<'PY' | tee /tmp/v49-decision.txt
from pathlib import Path
from statistics import median
ratios=[]
for t in ('std','cedar'):
    def med(a): return median(float(p.read_text().split()[0]) for p in Path('/tmp').glob(f'v49-{t}-{a}-*.time'))
    b=med('base'); c=med('minimal'); d=(c/b-1)*100; ratios.append(c/b)
    print(f'V49_{t.upper()}_BASE_WALL={b:.3f} MINIMAL_WALL={c:.3f} DELTA={d:+.3f}%')
mean=(sum(ratios)/len(ratios)-1)*100
print(f'V49_MEAN_NORMALIZED_DELTA={mean:+.3f}%')
if mean <= -2:
    print('DECISION=V49_COMPOUND_MATERIAL_WIN__FULL_MATHLIB_GATE')
elif mean < 0:
    print('DECISION=V49_COMPOUND_WEAK_WIN__FULL_MATHLIB_GATE_BEFORE_RETAIN')
else:
    print('DECISION=V49_INTERACTION_NEGATIVE__DO_NOT_COMPOUND__SHARED_TRAVERSAL_NEXT')
print('RULE=RETAIN_ONLY_VERIFIED_CONSEQUENTIAL_DISTINCTIONS')
PY
