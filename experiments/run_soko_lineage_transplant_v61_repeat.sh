#!/usr/bin/env bash
set -euxo pipefail

SOKO=7b51784fe4ec9b82bf7a20c71ba6bf803a4ed7c0
ROOT=/tmp/v61-repeat
rm -rf "$ROOT"
mkdir -p "$ROOT"

git clone https://github.com/intgrah/sokonanoda "$ROOT/soko"
git -C "$ROOT/soko" checkout "$SOKO"
cp -a "$ROOT/soko" "$ROOT/candidate"

python3 - "$ROOT/candidate" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/'src/eval.rs'
s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))

p=root/'src/relevance.rs'
s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
assert s.count(old)==1
p.write_text(s.replace(old,'                let _ = r;',1))
PY

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" rev-parse HEAD | tee "$ROOT/arena-head.txt"
cd "$ROOT/arena"
for t in init-prelude cedar mathlib; do nix develop -c ./lka.py build-test "$t"; done

build_arm() {
  local arm="$1" dir="$ROOT/$1" pgo="$ROOT/$1/pgo-repeat"
  rm -rf "$pgo" "$ROOT/target-$arm"
  mkdir -p "$pgo"
  cd "$dir"
  CARGO_TARGET_DIR="$ROOT/target-$arm" RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$pgo" cargo build --release --locked
  "$ROOT/target-$arm/release/sokonanoda" "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
  nix shell nixpkgs#llvmPackages_21.llvm -c llvm-profdata merge -o "$pgo/merged.profdata" "$pgo"
  test -s "$pgo/merged.profdata"
  rm -rf "$ROOT/target-$arm"
  CARGO_TARGET_DIR="$ROOT/target-$arm" RUSTFLAGS="-C target-cpu=native -Cprofile-use=$pgo/merged.profdata" cargo build --release --locked
  cp "$ROOT/target-$arm/release/sokonanoda" "$ROOT/$arm.bin"
}
for arm in soko candidate; do build_arm "$arm"; done

for t in cedar mathlib; do
  "$ROOT/soko.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" > "$ROOT/$t-soko.out" 2> "$ROOT/$t-soko.err"
  "$ROOT/candidate.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" > "$ROOT/$t-candidate.out" 2> "$ROOT/$t-candidate.err"
  cmp "$ROOT/$t-soko.out" "$ROOT/$t-candidate.out"
  echo "V61R_${t^^}_SEMANTIC_REPLAY=EXACT"
done

printf 'test,pass,arm,seconds\n' > "$ROOT/timings.csv"
orders=('soko candidate' 'candidate soko' 'soko candidate' 'candidate soko' 'soko candidate')
for t in cedar mathlib; do
  pass=0
  for order in "${orders[@]}"; do
    pass=$((pass+1))
    for arm in $order; do
      sec=$(/usr/bin/time -f '%e' -o "$ROOT/time.tmp" "$ROOT/$arm.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" >/dev/null 2>"$ROOT/$t-$arm-p$pass.err"; cat "$ROOT/time.tmp")
      printf '%s,%s,%s,%s\n' "$t" "$pass" "$arm" "$sec" >> "$ROOT/timings.csv"
    done
  done
done

python3 - <<'PY' | tee "$ROOT/summary.txt"
import csv,statistics,math
from collections import defaultdict
D=defaultdict(list)
for r in csv.DictReader(open('/tmp/v61-repeat/timings.csv')):
    D[(r['test'],r['arm'])].append(float(r['seconds']))
deltas=[]
for t in ('cedar','mathlib'):
    b=D[(t,'soko')]; c=D[(t,'candidate')]
    bm=statistics.median(b); cm=statistics.median(c)
    d=(cm/bm-1)*100; deltas.append(d)
    print(f'=== V61R_{t.upper()} ===')
    print(f'soko raw={b} median={bm:.3f}')
    print(f'candidate raw={c} median={cm:.3f}')
    print(f'V61R_{t.upper()}_DELTA={d:+.4f}%')
gm=(math.prod(1+d/100 for d in deltas)**0.5-1)*100
print(f'V61R_PAIR_GEOMEAN={gm:+.4f}%')
print('V61R_DELTAS=' + repr([round(x,4) for x in deltas]))
if deltas[1] <= -2.0 and deltas[0] <= 1.0:
    print('DECISION=V61R_MATHLIB_GAIN_REPEATS__PROMOTE_SOKO_PI_PROP_TO_ARENA_RELEASE_GATE')
else:
    print('DECISION=V61R_NOT_PROMOTION_GRADE__DO_NOT_BUMP_ARENA')
print('RULE=REPEAT_DECISIVE_BOUNDARY_BEFORE_PROMOTION')
PY

mkdir -p "$GITHUB_WORKSPACE/v61-repeat-artifact"
cp "$ROOT/timings.csv" "$ROOT/summary.txt" "$ROOT/arena-head.txt" "$ROOT"/*.err "$GITHUB_WORKSPACE/v61-repeat-artifact/" || true
