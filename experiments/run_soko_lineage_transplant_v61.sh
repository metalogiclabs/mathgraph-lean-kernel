#!/usr/bin/env bash
set -euxo pipefail

SOKO=7b51784fe4ec9b82bf7a20c71ba6bf803a4ed7c0
MG_BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
ROOT=/tmp/v61
rm -rf "$ROOT"
mkdir -p "$ROOT"

git clone https://github.com/intgrah/sokonanoda "$ROOT/soko"
git -C "$ROOT/soko" checkout "$SOKO"
cp -a "$ROOT/soko" "$ROOT/soko-pi"
cp -a "$ROOT/soko" "$ROOT/soko-pi-prop"
git worktree add "$ROOT/mathgraph" "$MG_BASE"

patch_pi() {
  local dir="$1"
  python3 - "$dir" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])/"src/eval.rs"
s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1, s.count(old)
p.write_text(s.replace(old,new,1))
PY
}

patch_prop_off() {
  local dir="$1"
  python3 - "$dir" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])/"src/relevance.rs"
s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
assert s.count(old)==1, s.count(old)
s=s.replace(old,'                let _ = r;',1)
p.write_text(s)
PY
}

patch_pi "$ROOT/soko-pi"
patch_pi "$ROOT/soko-pi-prop"
patch_prop_off "$ROOT/soko-pi-prop"
patch_pi "$ROOT/mathgraph"
patch_prop_off "$ROOT/mathgraph"

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
cd "$ROOT/arena"
for t in init-prelude std cedar mathlib cslib; do nix develop -c ./lka.py build-test "$t"; done

build_arm() {
  local arm="$1"
  local dir="$ROOT/$arm"
  local pgo="$dir/pgo-v61"
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

for arm in soko soko-pi soko-pi-prop mathgraph; do build_arm "$arm"; done

# Exact acceptance/output replay on every large valid workload.
for t in std cedar mathlib cslib; do
  ref=""
  for arm in soko soko-pi soko-pi-prop mathgraph; do
    "$ROOT/$arm.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" > "$ROOT/$t-$arm.out" 2> "$ROOT/$t-$arm.err"
    if [ -z "$ref" ]; then ref="$ROOT/$t-$arm.out"; else cmp "$ref" "$ROOT/$t-$arm.out"; fi
  done
  echo "V61_${t^^}_SEMANTIC_REPLAY=EXACT"
done

printf 'test,pass,arm,seconds\n' > "$ROOT/timings.csv"
orders=(
  'soko soko-pi soko-pi-prop mathgraph'
  'mathgraph soko-pi-prop soko-pi soko'
  'soko-pi soko mathgraph soko-pi-prop'
)
for t in std cedar mathlib cslib; do
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
import csv, statistics, math
from collections import defaultdict
rows=list(csv.DictReader(open('/tmp/v61/timings.csv')))
D=defaultdict(list)
for r in rows:D[(r['test'],r['arm'])].append(float(r['seconds']))
arms=['soko','soko-pi','soko-pi-prop','mathgraph']
tests=['std','cedar','mathlib','cslib']
med={}
for t in tests:
    print(f'=== {t.upper()} ===')
    for a in arms:
        xs=D[(t,a)]; m=statistics.median(xs); med[(t,a)]=m
        print(f'{a:16s} raw={xs} median={m:.3f}')
    base=med[(t,'soko')]
    for a in arms[1:]:
        d=(med[(t,a)]/base-1)*100
        print(f'V61_{t.upper()}_{a.upper().replace("-","_")}_VS_SOKO={d:+.4f}%')

def gm(arm):
    return math.prod(med[(t,arm)]/med[(t,'soko')] for t in tests)**(1/len(tests))
for a in arms[1:]: print(f'V61_GEOMEAN_{a.upper().replace("-","_")}_VS_SOKO={(gm(a)-1)*100:+.4f}%')
trans=[(med[(t,'soko-pi-prop')]/med[(t,'soko')]-1)*100 for t in tests]
mean=(math.prod(1+d/100 for d in trans)**(1/4)-1)*100
print('V61_TRANSPLANT_DELTAS=' + repr([round(x,4) for x in trans]))
print(f'V61_TRANSPLANT_GEOMEAN={mean:+.4f}%')
if mean <= -2.0 and max(trans) <= 1.0:
    print('DECISION=V61_TRANSPLANT_MATERIAL__PROMOTE_SOKO_PLUS_PI_PLUS_PROP_OFF_TO_FULL_ARENA_GATE')
elif mean <= -1.0 and max(trans) <= 1.0:
    print('DECISION=V61_TRANSPLANT_WEAK_POSITIVE__REPEAT_MATHLIB_CEDAR_BEFORE_PROMOTION')
else:
    print('DECISION=V61_TRANSPLANT_NOT_STABLE__DO_NOT_PROMOTE__READ_LINEAGE_DIFFERENTIAL')
print('RULE=COMPARE_SUBSTRATES_CAUSALLY__DO_NOT_INFER_FROM_OLD_LEADERBOARD_RUNS')
PY

mkdir -p "$GITHUB_WORKSPACE/v61-artifact"
cp "$ROOT/timings.csv" "$ROOT/summary.txt" "$ROOT"/*.err "$GITHUB_WORKSPACE/v61-artifact/" || true
