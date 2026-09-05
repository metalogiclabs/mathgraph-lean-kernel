#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v55-* 

for c in 16 32 64 128; do
  git worktree add "/tmp/v55-$c" "$BASE"
  python3 - "$c" "/tmp/v55-$c" <<'PY'
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

cat >/tmp/v55-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v55-arena
cd /tmp/v55-arena
for t in init-prelude mathlib; do nix develop -c ./lka.py build-test "$t"; done

# Arena-style PGO independently for each arm, trained on init-prelude.
for c in 16 32 64 128; do
  mkdir -p "/tmp/v55-$c-pgo"
  (cd "/tmp/v55-$c" && RUSTFLAGS="-C target-cpu=native -Cprofile-generate=/tmp/v55-$c-pgo" cargo build --release --locked)
  "/tmp/v55-$c/target/release/sokonanoda" /tmp/v55-config.json < /tmp/v55-arena/_build/tests/init-prelude.ndjson >/dev/null 2>"/tmp/v55-$c-train.err"
  llvm-profdata merge -o "/tmp/v55-$c-pgo/merged.profdata" "/tmp/v55-$c-pgo"
  (cd "/tmp/v55-$c" && RUSTFLAGS="-C target-cpu=native -Cprofile-use=/tmp/v55-$c-pgo/merged.profdata" cargo build --release --locked)
  cp "/tmp/v55-$c/target/release/sokonanoda" "/tmp/v55-$c-bin"
done

# Exact semantic replay against the current 64-declaration policy.
/tmp/v55-64-bin /tmp/v55-config.json < /tmp/v55-arena/_build/tests/mathlib.ndjson >/tmp/v55-64.out 2>/tmp/v55-64.err
for c in 16 32 128; do
  "/tmp/v55-$c-bin" /tmp/v55-config.json < /tmp/v55-arena/_build/tests/mathlib.ndjson >"/tmp/v55-$c.out" 2>"/tmp/v55-$c.err"
  cmp /tmp/v55-64.out "/tmp/v55-$c.out"
done
echo V55_MATHLIB_SEMANTIC_REPLAY=EXACT

# Alternating two-pass wall tournament to limit runner cost while exposing a large separator.
orders=("16 32 64 128" "128 64 32 16")
r=0
for order in "${orders[@]}"; do
  r=$((r+1))
  for c in $order; do
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v55-$c-$r.time" \
      "/tmp/v55-$c-bin" /tmp/v55-config.json < /tmp/v55-arena/_build/tests/mathlib.ndjson >/dev/null 2>"/tmp/v55-$c-$r.err"
  done
done

python3 - <<'PY' | tee /tmp/v55-decision.txt
from pathlib import Path
from statistics import median
vals={}
for c in (16,32,64,128):
    xs=[float(p.read_text().split()[0]) for p in sorted(Path('/tmp').glob(f'v55-{c}-*.time'))]
    assert len(xs)==2,(c,xs)
    vals[c]=median(xs)
    print(f'V55_TIMES chunk={c} raw={xs} median={vals[c]:.3f}')
w=min(vals,key=vals.get)
d=(vals[w]/vals[64]-1)*100
print(f'V55_WINNER chunk={w} delta_vs_64={d:+.4f}%')
if w != 64 and d <= -2.0:
    print('DECISION=V55_FIXED64_REJECTED__CHUNK_POLICY_CONSEQUENTIAL__ADVANCE_LOAD_BALANCE_CENSUS')
elif w != 64 and d < 0:
    print('DECISION=V55_ALT_CHUNK_WEAK_WIN__REPEAT_BEFORE_RETAINING')
else:
    print('DECISION=V55_FIXED64_SUPPORTED__DO_NOT_ADD_CHUNK_DISTINCTION')
print('RULE=DO_NOT_CREATE_WORK_WEIGHTING_UNLESS_FIXED_CHUNK_FAILURE_FORCES_IT')
PY
