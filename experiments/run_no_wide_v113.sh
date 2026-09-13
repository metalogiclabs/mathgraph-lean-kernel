#!/usr/bin/env bash
set -euo pipefail
BASE=611f607a6cf6150fd341330cfcfcedd7a4b4453f
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/no-wide-v113
rm -rf "$ROOT"
mkdir -p "$ROOT/out"

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/nowide"
git -C "$ROOT/nowide" checkout -q "$BASE"
cd "$ROOT/nowide"
python3 "$GITHUB_WORKSPACE/scripts/apply_no_wide_v113.py"

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
for t in mathlib con-leche perf/app-lam perf/beta-ladder; do
  echo "V113_BUILD_TEST=$t"
  nix develop -c ./lka.py build-test "$t" >/dev/null
done

build_pgo() {
  local dir="$1"
  local tag="$2"
  cd "$dir"
  rm -rf pgo
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$dir/pgo" cargo build --release --locked -q
  target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
  cd "$ROOT/arena"
  nix develop -c llvm-profdata merge -o "$dir/pgo/merged.profdata" "$dir/pgo"
  cd "$dir"
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=$dir/pgo/merged.profdata" cargo build --release --locked -q
  echo "V113_PGO_$tag=PASS"
}
build_pgo "$ROOT/base" BASE
build_pgo "$ROOT/nowide" NOWIDE

run_one() {
  local tag="$1"; local dir="$2"; local test="$3"; local timeout_s="$4"
  local safe="$(printf '%s' "$test" | tr '/' '_')"
  local out="$ROOT/out/${tag}__${safe}"
  echo "V113_BEGIN tag=$tag test=$test"
  set +e
  /usr/bin/time -f 'wall=%e rss_kb=%M user=%U sys=%S' -o "$out.time"     timeout "$timeout_s" "$dir/target/release/sokonanoda" "$ROOT/config.json"     < "$ROOT/arena/_build/tests/$test.ndjson" >"$out.stdout" 2>"$out.stderr"
  rc=$?
  set -e
  stats="$(cat "$out.time")"
  echo "V113_RESULT tag=$tag test=$test rc=$rc $stats"
  return "$rc"
}

for t in perf/app-lam perf/beta-ladder con-leche mathlib; do
  timeout_s=600
  [ "$t" = "con-leche" ] && timeout_s=1800
  [ "$t" = "mathlib" ] && timeout_s=3600
  run_one BASE "$ROOT/base" "$t" "$timeout_s"
  run_one NOWIDE "$ROOT/nowide" "$t" "$timeout_s"
done

echo "V113_COMPLETE=PASS"
