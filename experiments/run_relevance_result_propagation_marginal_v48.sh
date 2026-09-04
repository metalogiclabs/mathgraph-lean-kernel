#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v48-* /tmp/v48-arena
for arm in base terminal; do git worktree add "/tmp/v48-$arm" "$BASE"; done

for d in /tmp/v48-base /tmp/v48-terminal; do
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

# Keep terminal result classification, but remove backward imax propagation through binder domains.
# Missing propagated result facts are conservative unknowns, never false irrelevance claims.
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v48-terminal/src/relevance.rs'); s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
new='''                let _ = r;'''
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY

cat >/tmp/v48-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v48-arena
(cd /tmp/v48-arena && for t in std cedar; do nix develop -c ./lka.py build-test "$t"; done)

for arm in base terminal; do
  (cd "/tmp/v48-$arm" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
  cp "/tmp/v48-$arm/target/release/sokonanoda" "/tmp/v48-$arm-bin"
done

for t in std cedar; do
  /tmp/v48-base-bin /tmp/v48-config.json < "/tmp/v48-arena/_build/tests/$t.ndjson" >"/tmp/v48-$t-base.out" 2>"/tmp/v48-$t-base.err"
  /tmp/v48-terminal-bin /tmp/v48-config.json < "/tmp/v48-arena/_build/tests/$t.ndjson" >"/tmp/v48-$t-terminal.out" 2>"/tmp/v48-$t-terminal.err"
  cmp "/tmp/v48-$t-base.out" "/tmp/v48-$t-terminal.out"
  echo "V48_${t^^}_SEMANTIC_REPLAY=EXACT"
  for arm in base terminal terminal base; do
    n=$(find /tmp -maxdepth 1 -type f -name "v48-${t}-${arm}-*.time" | wc -l); n=$((n+1))
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v48-${t}-${arm}-${n}.time" "/tmp/v48-$arm-bin" /tmp/v48-config.json < "/tmp/v48-arena/_build/tests/$t.ndjson" >/dev/null 2>"/tmp/v48-${t}-${arm}-${n}.err"
  done
done

python3 - <<'PY' | tee /tmp/v48-decision.txt
from pathlib import Path
from statistics import median
ratios=[]
for t in ('std','cedar'):
    def med(a): return median(float(p.read_text().split()[0]) for p in Path('/tmp').glob(f'v48-{t}-{a}-*.time'))
    b=med('base'); c=med('terminal'); d=(c/b-1)*100; ratios.append(c/b)
    print(f'V48_{t.upper()}_BASE_WALL={b:.3f} TERMINAL_ONLY_WALL={c:.3f} DELTA={d:+.3f}%')
mean=(sum(ratios)/len(ratios)-1)*100
print(f'V48_MEAN_NORMALIZED_DELTA={mean:+.3f}%')
if mean >= 2:
    print('DECISION=V48_BACKWARD_RESULT_PROPAGATION_PAYS__RETAIN_PROPAGATION')
elif mean <= -2:
    print('DECISION=V48_BACKWARD_RESULT_PROPAGATION_NET_TAX__REMOVE_OR_REDESIGN')
else:
    print('DECISION=V48_PROPAGATION_NEAR_BREAK_EVEN__SHARED_TELESCOPE_TRAVERSAL_DOMINATES_NEXT')
print('RULE=UNKNOWN_IS_CONSERVATIVE__NO_NEW_DISTINCTION_WITHOUT_VERIFIED_FAILURE')
PY
