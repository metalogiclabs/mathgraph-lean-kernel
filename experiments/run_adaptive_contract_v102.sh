#!/usr/bin/env bash
set -euo pipefail

ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
BASE=d6a73279e6765e637f9741180cefbd7ef957d8e5
ROOT=/tmp/v102-contract
rm -rf "$ROOT"
mkdir -p "$ROOT/out"

echo "V102_CANDIDATE=$(git rev-parse HEAD)"
echo "V102_BASE=$BASE"
echo "V102_ARENA=$ARENA"

cargo test --release --locked -q
echo "V102_SOURCE_TESTS=PASS"

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"

cd "$ROOT/arena"
for t in init-prelude perf/app-lam perf/beta-ladder perf/let-ladder con-leche mathlib; do
  echo "V102_BUILD_TEST=$t"
  nix develop -c ./lka.py build-test "$t" >/dev/null
done

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$GITHUB_WORKSPACE"
git worktree add --detach "$ROOT/base" "$BASE" >/dev/null

build_pgo () {
  local label="$1"
  local dir="$2"
  echo "V102_BUILD_BEGIN=$label"
  cd "$dir"
  rm -rf pgo target/release/sokonanoda
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$dir/pgo" cargo build --release --locked -q
  target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
  cd "$ROOT/arena"
  nix develop -c llvm-profdata merge -o "$dir/pgo/merged.profdata" "$dir/pgo"
  cd "$dir"
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=$dir/pgo/merged.profdata" cargo build --release --locked -q
  cp target/release/sokonanoda "$ROOT/$label.bin"
  echo "V102_BUILD_PASS=$label"
}

build_pgo baseline "$ROOT/base"
build_pgo candidate "$GITHUB_WORKSPACE"

if perf stat -e instructions true >/dev/null 2>"$ROOT/perf-probe"; then
  HAVE_PERF=1
  echo "V102_PERF_INSTRUCTIONS=AVAILABLE"
else
  HAVE_PERF=0
  echo "V102_PERF_INSTRUCTIONS=UNAVAILABLE"
fi

bench () {
  local label="$1"
  local bin="$2"
  local test="$3"
  local timeout_s="$4"
  local rounds="$5"
  local input="$ROOT/arena/_build/tests/$test.ndjson"
  for round in $(seq 1 "$rounds"); do
    local timefile="$ROOT/out/$label-$test-$round.time"
    local perffile="$ROOT/out/$label-$test-$round.perf"
    local rc=0
    if [ "$HAVE_PERF" -eq 1 ]; then
      set +e
      /usr/bin/time -f 'elapsed_s=%e rss_kb=%M user_s=%U sys_s=%S' -o "$timefile" \
        perf stat -x, -e instructions -o "$perffile" \
        timeout "$timeout_s" "$bin" "$ROOT/config.json" < "$input" >/dev/null
      rc=$?
      set -e
    else
      set +e
      /usr/bin/time -f 'elapsed_s=%e rss_kb=%M user_s=%U sys_s=%S' -o "$timefile" \
        timeout "$timeout_s" "$bin" "$ROOT/config.json" < "$input" >/dev/null
      rc=$?
      set -e
    fi
    echo -n "V102_RESULT label=$label test=$test round=$round rc=$rc "
    tr '\n' ' ' < "$timefile"
    if [ "$HAVE_PERF" -eq 1 ] && [ -s "$perffile" ]; then
      inst=$(awk -F, '$3 ~ /instructions/ {gsub(/ /,"",$1); print $1; exit}' "$perffile")
      echo " instructions=${inst:-NA}"
    else
      echo
    fi
    [ "$rc" -eq 0 ] || exit "$rc"
  done
}

for t in perf/app-lam perf/beta-ladder perf/let-ladder; do
  bench baseline "$ROOT/baseline.bin" "$t" 30 5
  bench candidate "$ROOT/candidate.bin" "$t" 30 5
done

bench baseline "$ROOT/baseline.bin" con-leche 180 3
bench candidate "$ROOT/candidate.bin" con-leche 180 3
bench baseline "$ROOT/baseline.bin" mathlib 300 3
bench candidate "$ROOT/candidate.bin" mathlib 300 3

echo "V102_CONTRACT_GATE=PASS"
