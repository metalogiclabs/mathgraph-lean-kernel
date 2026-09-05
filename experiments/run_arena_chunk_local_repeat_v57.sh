#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v57-*

for c in 64 128; do
  git worktree add "/tmp/v57-$c" "$BASE"
  python3 - "$c" "/tmp/v57-$c" <<'PY'
from pathlib import Path
import sys
c=sys.argv[1]; root=Path(sys.argv[2])
# Frozen semantic incumbent: Pi fast path + relevance propagation-off.
p=root/'src/eval.rs'; s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
p=root/'src/relevance.rs'; s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
assert s.count(old)==1
p.write_text(s.replace(old,'                let _ = r;',1))
# Sole experimental distinction.
p=root/'src/tc.rs'; s=p.read_text()
old='const CHUNK_SIZE: usize = 64;'
assert s.count(old)==1
p.write_text(s.replace(old,f'const CHUNK_SIZE: usize = {c};',1))
PY
done

cat >/tmp/v57-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v57-arena
cd /tmp/v57-arena
for t in init-prelude mathlib; do nix develop -c ./lka.py build-test "$t"; done

# Arena-style init-prelude PGO independently for each arm.
for c in 64 128; do
  mkdir -p "/tmp/v57-$c-pgo"
  (cd "/tmp/v57-$c" && RUSTFLAGS="-C target-cpu=native -Cprofile-generate=/tmp/v57-$c-pgo" cargo build --release --locked)
  "/tmp/v57-$c/target/release/sokonanoda" /tmp/v57-config.json < /tmp/v57-arena/_build/tests/init-prelude.ndjson >/dev/null 2>"/tmp/v57-$c-train.err"
  llvm-profdata merge -o "/tmp/v57-$c-pgo/merged.profdata" "/tmp/v57-$c-pgo"
  (cd "/tmp/v57-$c" && RUSTFLAGS="-C target-cpu=native -Cprofile-use=/tmp/v57-$c-pgo/merged.profdata" cargo build --release --locked)
  cp "/tmp/v57-$c/target/release/sokonanoda" "/tmp/v57-$c-bin"
done

# Semantic replay must be byte-identical.
/tmp/v57-64-bin /tmp/v57-config.json < /tmp/v57-arena/_build/tests/mathlib.ndjson >/tmp/v57-64.out 2>/tmp/v57-64.err
/tmp/v57-128-bin /tmp/v57-config.json < /tmp/v57-arena/_build/tests/mathlib.ndjson >/tmp/v57-128.out 2>/tmp/v57-128.err
cmp /tmp/v57-64.out /tmp/v57-128.out
echo V57_MATHLIB_SEMANTIC_REPLAY=EXACT

# Four balanced passes: enough to test whether the v55 separator repeats without widening representation.
orders=("64 128" "128 64" "64 128" "128 64")
r=0
for order in "${orders[@]}"; do
  r=$((r+1))
  for c in $order; do
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v57-$c-$r.time" \
      "/tmp/v57-$c-bin" /tmp/v57-config.json < /tmp/v57-arena/_build/tests/mathlib.ndjson >/dev/null 2>"/tmp/v57-$c-$r.err"
  done
done

python3 - <<'PY' | tee /tmp/v57-decision.txt
from pathlib import Path
from statistics import median
vals={}
raw={}
for c in (64,128):
    xs=[float(Path(f'/tmp/v57-{c}-{r}.time').read_text().split()[0]) for r in range(1,5)]
    raw[c]=xs
    vals[c]=median(xs)
    print(f'V57_TIMES chunk={c} raw={xs} median={vals[c]:.3f}')
d=(vals[128]/vals[64]-1)*100
wins=sum(a < b for a,b in zip(raw[128],raw[64]))
paired=[(a/b-1)*100 for a,b in zip(raw[128],raw[64])]
print(f'V57_DELTA_128_VS_64={d:+.4f}% pass_wins_128={wins}/4 paired_deltas={[round(x,4) for x in paired]}')
if d <= -2.0 and wins >= 3:
    print('DECISION=V57_FIXED128_CONFIRMED__RETAIN_CHUNK128__DO_NOT_CREATE_WORK_WEIGHTING')
elif abs(d) < 2.0:
    print('DECISION=V57_CHUNK_GAIN_NOT_STABLE__NO_MATERIAL_64_128_SEPARATOR__DO_NOT_CREATE_WORK_WEIGHTING')
else:
    print('DECISION=V57_CHUNK_RESULT_INCONSISTENT__REPEAT_ONLY_IF_POLICY_DECISION_REQUIRES_IT')
print('CENSUS_CONTEXT=FINISH_SKEW_64_0.0155PCT__128_0.0248PCT__WORK_WEIGHTING_NOT_LICENSED')
PY
