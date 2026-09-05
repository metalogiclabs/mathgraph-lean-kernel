#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
CHUNKS=(16 32 64 128 256)
rm -rf /tmp/v55-* 

cat >/tmp/v55-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v55-arena
cd /tmp/v55-arena
for t in init-prelude mathlib; do nix develop -c ./lka.py build-test "$t"; done
cd -

for c in "${CHUNKS[@]}"; do
  d="/tmp/v55-c$c"
  git worktree add "$d" "$BASE"
  python3 - "$d" "$c" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1]); chunk=sys.argv[2]
p=root/'src/eval.rs'; s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
p=root/'src/relevance.rs'; s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
assert s.count(old)==1
p.write_text(s.replace(old,'                let _ = r;',1))
p=root/'src/tc.rs'; s=p.read_text()
old='const CHUNK_SIZE: usize = 64;'
assert s.count(old)==1
p.write_text(s.replace(old,f'const CHUNK_SIZE: usize = {chunk};',1))
PY

  prof="/tmp/v55-pgo-c$c"; mkdir -p "$prof"
  (cd "$d" && RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$prof" cargo build --release --locked)
  "$d/target/release/sokonanoda" /tmp/v55-config.json < /tmp/v55-arena/_build/tests/init-prelude.ndjson >/dev/null 2>"/tmp/v55-c$c-train.err"
  llvm-profdata merge -o "$prof/merged.profdata" "$prof"
  (cd "$d" && RUSTFLAGS="-C target-cpu=native -Cprofile-use=$prof/merged.profdata" cargo build --release --locked)
  cp "$d/target/release/sokonanoda" "/tmp/v55-bin-c$c"
done

# Exact replay against the current CHUNK_SIZE=64 arm.
/tmp/v55-bin-c64 /tmp/v55-config.json < /tmp/v55-arena/_build/tests/mathlib.ndjson >/tmp/v55-ref.out 2>/tmp/v55-ref.err
for c in "${CHUNKS[@]}"; do
  /tmp/v55-bin-c$c /tmp/v55-config.json < /tmp/v55-arena/_build/tests/mathlib.ndjson >"/tmp/v55-c$c.out" 2>"/tmp/v55-c$c.err"
  cmp /tmp/v55-ref.out "/tmp/v55-c$c.out"
done
echo V55_MATHLIB_SEMANTIC_REPLAY=EXACT

# Rotate order over three rounds to reduce order bias.
orders=("16 32 64 128 256" "256 128 64 32 16" "64 16 128 32 256")
r=0
for order in "${orders[@]}"; do
  r=$((r+1))
  for c in $order; do
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v55-c$c-r$r.time" \
      "/tmp/v55-bin-c$c" /tmp/v55-config.json < /tmp/v55-arena/_build/tests/mathlib.ndjson >/dev/null 2>"/tmp/v55-c$c-r$r.err"
  done
done

python3 - <<'PY' | tee /tmp/v55-decision.txt
from pathlib import Path
from statistics import median
vals={}
for c in (16,32,64,128,256):
    xs=[float(p.read_text().split()[0]) for p in sorted(Path('/tmp').glob(f'v55-c{c}-r*.time'))]
    vals[c]=median(xs)
    print(f'V55_TIMES chunk={c} raw={xs} median={vals[c]:.3f}')
w=min(vals,key=vals.get); base=vals[64]
d=(vals[w]/base-1)*100
print(f'V55_WINNER chunk={w} median={vals[w]:.3f} delta_vs_64={d:+.4f}%')
if w != 64 and d <= -2.0:
    print('DECISION=V55_CHUNK_SIZE_MATERIAL_WIN__PROMOTE_AND_FULL_ARENA_SCORE')
elif w != 64 and d < 0:
    print('DECISION=V55_CHUNK_SIZE_WEAK_WIN__RETAIN_ONLY_IF_FULL_ARENA_SCORE_TRANSFERS')
else:
    print('DECISION=V55_CHUNK64_SUPPORTED__FIXED_DECLARATION_CHUNK_NOT_CURRENT_LIMITER')
print('RULE=ONLY_CREATE_WORK_WEIGHTING_IF_FIXED_SIZE_TOURNAMENT_EXPOSES_MATERIAL_IMBALANCE')
PY
