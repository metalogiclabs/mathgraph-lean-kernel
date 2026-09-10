#!/usr/bin/env bash
set -euo pipefail
ARENA=92fba121dcd26902a0193c40485b3140af95e898
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
CAND=d6a73279e6765e637f9741180cefbd7ef957d8e5
ROOT=/tmp/v101-mathlib
rm -rf "$ROOT" && mkdir -p "$ROOT/out"
echo "V101_MATHLIB_BASE=$BASE"
echo "V101_MATHLIB_CAND=$CAND"
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
nix develop -c ./lka.py build-test mathlib >/dev/null

build_one() {
  name="$1"; rev="$2"; dir="$ROOT/$name"
  git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$dir"
  git -C "$dir" checkout -q "$rev"
  cat >"$dir/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
  cd "$dir"
  rm -rf pgo
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$dir/pgo" cargo build --release --locked -q
  target/release/sokonanoda config.json < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
  cd "$ROOT/arena"
  nix develop -c llvm-profdata merge -o "$dir/pgo/merged.profdata" "$dir/pgo"
  cd "$dir"
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=$dir/pgo/merged.profdata" cargo build --release --locked -q
  echo "V101_MATHLIB_BUILD_${name}=PASS"
}
build_one base "$BASE"
build_one cand "$CAND"

# Try to expose PMU counters; failure is non-fatal, wall/RSS comparison still runs.
sudo sysctl -w kernel.perf_event_paranoid=-1 >/dev/null 2>&1 || true
run_one() {
  name="$1"; dir="$ROOT/$name"
  echo "V101_MATHLIB_BEGIN_${name}"
  cd "$dir"
  set +e
  /usr/bin/time -v perf stat -x, -e instructions -o "$ROOT/out/${name}.perf" -- target/release/sokonanoda config.json < "$ROOT/arena/_build/tests/mathlib.ndjson" >"$ROOT/out/${name}.out" 2>"$ROOT/out/${name}.time"
  rc=$?
  set -e
  echo "V101_MATHLIB_EXIT_${name}=$rc"
  cat "$ROOT/out/${name}.perf" | sed "s/^/V101_MATHLIB_PERF_${name}=/" || true
  grep "Maximum resident set size" "$ROOT/out/${name}.time" | sed "s/^/V101_MATHLIB_${name}_/" || true
  grep "Elapsed (wall clock) time" "$ROOT/out/${name}.time" | sed "s/^/V101_MATHLIB_${name}_/" || true
  [ "$rc" -eq 0 ] || exit "$rc"
  echo "V101_MATHLIB_${name}=PASS"
}
run_one base
run_one cand
python3 - "$ROOT/out/base.perf" "$ROOT/out/cand.perf" <<'PY'
import re,sys
def read(p):
    s=open(p).read()
    for line in s.splitlines():
        parts=line.split(",")
        if len(parts)>=3 and "instructions" in parts[2]:
            v=parts[0].strip().replace(",","")
            if v.isdigit(): return int(v)
    return None
b=read(sys.argv[1]); c=read(sys.argv[2])
print(f"V101_MATHLIB_BASE_INSTR={b}")
print(f"V101_MATHLIB_CAND_INSTR={c}")
if b and c:
    ratio=c/b
    projected=819210238451*ratio
    print(f"V101_MATHLIB_RATIO={ratio:.9f}")
    print(f"V101_MATHLIB_PROJECTED_ARENA_INSTR={projected:.0f}")
    print(f"V101_MATHLIB_NANOCLO_MARGIN={2842578264594/projected:.6f}")
PY
echo "V101_MATHLIB_AB_GATE=PASS"
