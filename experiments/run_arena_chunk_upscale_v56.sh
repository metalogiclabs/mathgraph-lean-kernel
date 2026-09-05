#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v56-*

for c in 64 128 256 512; do
  git worktree add "/tmp/v56-$c" "$BASE"
  python3 - "$c" "/tmp/v56-$c" <<'PY'
from pathlib import Path
import sys
c=sys.argv[1]; root=Path(sys.argv[2])
# Verified semantic incumbent: Pi-only + relevance propagation-off.
p=root/'src/eval.rs'; s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
p=root/'src/relevance.rs'; s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
assert s.count(old)==1
p.write_text(s.replace(old,'                let _ = r;',1))
# Only experimental distinction: fixed declaration chunk size.
p=root/'src/tc.rs'; s=p.read_text()
old='const CHUNK_SIZE: usize = 64;'
assert s.count(old)==1
p.write_text(s.replace(old,f'const CHUNK_SIZE: usize = {c};',1))
PY
done

cat >/tmp/v56-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v56-arena
cd /tmp/v56-arena
for t in init-prelude mathlib; do nix develop -c ./lka.py build-test "$t"; done

for c in 64 128 256 512; do
  mkdir -p "/tmp/v56-$c-pgo"
  (cd "/tmp/v56-$c" && RUSTFLAGS="-C target-cpu=native -Cprofile-generate=/tmp/v56-$c-pgo" cargo build --release --locked)
  "/tmp/v56-$c/target/release/sokonanoda" /tmp/v56-config.json < /tmp/v56-arena/_build/tests/init-prelude.ndjson >/dev/null 2>"/tmp/v56-$c-train.err"
  llvm-profdata merge -o "/tmp/v56-$c-pgo/merged.profdata" "/tmp/v56-$c-pgo"
  (cd "/tmp/v56-$c" && RUSTFLAGS="-C target-cpu=native -Cprofile-use=/tmp/v56-$c-pgo/merged.profdata" cargo build --release --locked)
  cp "/tmp/v56-$c/target/release/sokonanoda" "/tmp/v56-$c-bin"
done

# Exact semantic replay against v55 winner, chunk=128.
/tmp/v56-128-bin /tmp/v56-config.json < /tmp/v56-arena/_build/tests/mathlib.ndjson >/tmp/v56-128.out 2>/tmp/v56-128.err
for c in 64 256 512; do
  "/tmp/v56-$c-bin" /tmp/v56-config.json < /tmp/v56-arena/_build/tests/mathlib.ndjson >"/tmp/v56-$c.out" 2>"/tmp/v56-$c.err"
  cmp /tmp/v56-128.out "/tmp/v56-$c.out"
done
echo V56_MATHLIB_SEMANTIC_REPLAY=EXACT

orders=("64 128 256 512" "512 256 128 64")
r=0
for order in "${orders[@]}"; do
  r=$((r+1))
  for c in $order; do
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v56-$c-$r.time" \
      "/tmp/v56-$c-bin" /tmp/v56-config.json < /tmp/v56-arena/_build/tests/mathlib.ndjson >/dev/null 2>"/tmp/v56-$c-$r.err"
  done
done

python3 - <<'PY' | tee /tmp/v56-decision.txt
from pathlib import Path
from statistics import median
vals={}
for c in (64,128,256,512):
    xs=[float(p.read_text().split()[0]) for p in sorted(Path('/tmp').glob(f'v56-{c}-*.time'))]
    assert len(xs)==2,(c,xs)
    vals[c]=median(xs)
    print(f'V56_TIMES chunk={c} raw={xs} median={vals[c]:.3f}')
w=min(vals,key=vals.get)
d128=(vals[w]/vals[128]-1)*100
print(f'V56_WINNER chunk={w} delta_vs_128={d128:+.4f}%')
if w > 128 and d128 <= -2.0:
    print('DECISION=V56_LARGER_FIXED_CHUNK_MATERIAL_WIN__RETAIN_WINNER_BEFORE_WORK_WEIGHTING')
elif w > 128 and d128 < 0:
    print('DECISION=V56_LARGER_FIXED_CHUNK_WEAK_WIN__REPEAT_BEFORE_RETAINING')
elif w == 128:
    print('DECISION=V56_CHUNK128_SUPPORTED__NEXT_CENSUS_STRAGGLER_STRUCTURE')
else:
    print('DECISION=V56_NONMONOTONE_CHUNK_RESPONSE__CENSUS_LOAD_BALANCE_BEFORE_POLICY_CHANGE')
print('RULE=DO_NOT_ADD_WORK_WEIGHTING_UNTIL_FIXED_CHUNK_SCALE_IS_EXHAUSTED')
PY
