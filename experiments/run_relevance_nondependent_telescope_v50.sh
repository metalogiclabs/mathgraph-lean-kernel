#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v50-* /tmp/v50-arena
for arm in base bypass; do git worktree add "/tmp/v50-$arm" "$BASE"; done

for d in /tmp/v50-base /tmp/v50-bypass; do
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

# v49 minimal relevance core in candidate: no arg-domain level classification,
# no backward result propagation; retain terminal result classification.
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v50-bypass/src/relevance.rs'); s=p.read_text()
old='''            let d = *domain;\n            dom.push(self.level_of_type(depth, d));\n            let fresh = self.mk_bvar_hc(depth, d);\n            cur = self.apply_closure(depth + 1, body, fresh, Some(d));\n            depth += 1;'''
new='''            let d = *domain;\n            dom.push(None);\n            if body.ctx.is_none() && self.ctx.num_loose_bvars(body.body) == 0 {\n                cur = self.eval(depth, body.env, body.body);\n            } else {\n                let fresh = self.mk_bvar_hc(depth, d);\n                cur = self.apply_closure(depth + 1, body, fresh, Some(d));\n            }\n            depth += 1;'''
assert s.count(old)==1
s=s.replace(old,new,1)
old2='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
assert s.count(old2)==1
s=s.replace(old2,'                let _ = r;',1)
p.write_text(s)
PY

cat >/tmp/v50-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v50-arena
(cd /tmp/v50-arena && for t in std cedar; do nix develop -c ./lka.py build-test "$t"; done)
for arm in base bypass; do
  (cd "/tmp/v50-$arm" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
  cp "/tmp/v50-$arm/target/release/sokonanoda" "/tmp/v50-$arm-bin"
done
for t in std cedar; do
  /tmp/v50-base-bin /tmp/v50-config.json < "/tmp/v50-arena/_build/tests/$t.ndjson" >"/tmp/v50-$t-base.out" 2>"/tmp/v50-$t-base.err"
  /tmp/v50-bypass-bin /tmp/v50-config.json < "/tmp/v50-arena/_build/tests/$t.ndjson" >"/tmp/v50-$t-bypass.out" 2>"/tmp/v50-$t-bypass.err"
  cmp "/tmp/v50-$t-base.out" "/tmp/v50-$t-bypass.out"
  echo "V50_${t^^}_SEMANTIC_REPLAY=EXACT"
  for arm in base bypass bypass base; do
    n=$(find /tmp -maxdepth 1 -type f -name "v50-${t}-${arm}-*.time" | wc -l); n=$((n+1))
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v50-${t}-${arm}-${n}.time" "/tmp/v50-$arm-bin" /tmp/v50-config.json < "/tmp/v50-arena/_build/tests/$t.ndjson" >/dev/null 2>"/tmp/v50-${t}-${arm}-${n}.err"
  done
done
python3 - <<'PY' | tee /tmp/v50-decision.txt
from pathlib import Path
from statistics import median
rat=[]
for t in ('std','cedar'):
    def med(a): return median(float(p.read_text().split()[0]) for p in Path('/tmp').glob(f'v50-{t}-{a}-*.time'))
    b=med('base'); c=med('bypass'); d=(c/b-1)*100; rat.append(c/b)
    print(f'V50_{t.upper()}_BASE_WALL={b:.3f} BYPASS_WALL={c:.3f} DELTA={d:+.3f}%')
mean=(sum(rat)/len(rat)-1)*100
print(f'V50_MEAN_NORMALIZED_DELTA={mean:+.3f}%')
if mean <= -2: print('DECISION=V50_NONDEPENDENT_BYPASS_MATERIAL__FULL_MATHLIB_GATE')
elif mean < 0: print('DECISION=V50_NONDEPENDENT_BYPASS_WEAK__RETAIN_ONLY_IF_TRANSFER')
else: print('DECISION=V50_NO_GAIN__DEPENDENCY_SPLIT_NOT_THE_TAX')
print('RULE=CREATE_ONLY_DISTINCTIONS_FORCED_BY_VERIFIED_FAILURE')
PY
