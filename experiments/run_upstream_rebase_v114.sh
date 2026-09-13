#!/usr/bin/env bash
set -euo pipefail
BASE=28c03d0103e004610e4d47a4828965efb2b70af9
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/upstream-rebase-v114
rm -rf "$ROOT"
mkdir -p "$ROOT/out"

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"

python3 scripts/apply_equal_hint_v114.py
cargo test --release --locked -q

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
for t in mathlib perf/magma-list-pair-n21 perf/beta-ladder; do
  echo "V114_BUILD_TEST=$t"
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
  echo "V114_PGO_$tag=PASS"
}
build_pgo "$ROOT/base" BASE
build_pgo "$GITHUB_WORKSPACE" CANDIDATE

run_one() {
  local tag="$1"; local dir="$2"; local test="$3"; local timeout_s="$4"
  local safe
  safe="$(printf '%s' "$test" | tr '/' '_')"
  local out="$ROOT/out/${tag}__${safe}"
  echo "V114_BEGIN tag=$tag test=$test"
  set +e
  /usr/bin/time -f 'wall=%e rss_kb=%M user=%U sys=%S' -o "$out.time" \
    timeout "$timeout_s" "$dir/target/release/sokonanoda" "$ROOT/config.json" \
    < "$ROOT/arena/_build/tests/$test.ndjson" >"$out.stdout" 2>"$out.stderr"
  rc=$?
  set -e
  echo "V114_RESULT tag=$tag test=$test rc=$rc $(cat "$out.time")"
  return "$rc"
}

for t in perf/beta-ladder perf/magma-list-pair-n21 mathlib; do
  timeout_s=900
  [ "$t" = "mathlib" ] && timeout_s=3600
  run_one BASE "$ROOT/base" "$t" "$timeout_s"
  run_one CANDIDATE "$GITHUB_WORKSPACE" "$t" "$timeout_s"
done

echo "V114_COMPLETE=PASS"
