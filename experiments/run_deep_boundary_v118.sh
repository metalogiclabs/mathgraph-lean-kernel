#!/usr/bin/env bash
set -euo pipefail

BASE=d6a73279e6765e637f9741180cefbd7ef957d8e5
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/deep-boundary-v118
rm -rf "$ROOT"
mkdir -p "$ROOT/out" "$ROOT/report"

echo "V118_HEAD=$(git rev-parse HEAD)"
echo "V118_BASE=$BASE"
echo "V118_ARENA=$ARENA"

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"

python3 scripts/apply_deep_boundary_selector_v118.py
cargo test --release --locked -q
echo "V118_SELECTOR_COMPILE=PASS"

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
for t in mathlib con-leche perf/beta-ladder perf/app-lam; do
  echo "V118_BUILD_TEST=$t"
  nix develop -c ./lka.py build-test "$t" >/dev/null
done

build_pgo () {
  local dir="$1"
  local tag="$2"
  cd "$dir"
  rm -rf pgo
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$dir/pgo" cargo build --release --locked -q
  env MATHGRAPH_V118_THRESHOLD_MILLI=0 target/release/sokonanoda "$ROOT/config.json" \
    < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null 2>/dev/null
  cd "$ROOT/arena"
  nix develop -c llvm-profdata merge -o "$dir/pgo/merged.profdata" "$dir/pgo"
  cd "$dir"
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=$dir/pgo/merged.profdata" cargo build --release --locked -q
  echo "V118_PGO_$tag=PASS"
}

build_pgo "$ROOT/base" BASE
build_pgo "$GITHUB_WORKSPACE" SELECTOR

run_one () {
  local tag="$1"
  local dir="$2"
  local test="$3"
  local threshold="$4"
  local timeout_s="$5"
  local safe
  safe="$(printf '%s' "$test" | tr '/' '_')"
  local out="$ROOT/out/${tag}__${threshold}__${safe}"
  echo "V118_BEGIN tag=$tag test=$test threshold=$threshold"
  set +e
  env MATHGRAPH_V118_THRESHOLD_MILLI="$threshold" \
    /usr/bin/time -f 'wall=%e rss_kb=%M user=%U sys=%S' -o "$out.time" \
    timeout "$timeout_s" "$dir/target/release/sokonanoda" "$ROOT/config.json" \
    < "$ROOT/arena/_build/tests/$test.ndjson" >"$out.stdout" 2>"$out.stderr"
  rc=$?
  set -e
  if [ -s "$out.time" ]; then
    echo "V118_RESULT tag=$tag test=$test threshold=$threshold rc=$rc $(cat "$out.time")" | tee -a "$ROOT/report/results.txt"
  else
    echo "V118_RESULT tag=$tag test=$test threshold=$threshold rc=$rc wall=$timeout_s rss_kb=0 user=0 sys=0" | tee -a "$ROOT/report/results.txt"
  fi
}

for t in perf/app-lam perf/beta-ladder con-leche mathlib; do
  timeout_s=240
  [ "$t" = "con-leche" ] && timeout_s=240
  [ "$t" = "mathlib" ] && timeout_s=240
  run_one BASE "$ROOT/base" "$t" 0 "$timeout_s"
done

# Frozen generic structural-yield thresholds from V117:
# 0 = existing full-wide control; 100,250,500,1000,2000 = increasingly selective.
for threshold in 0 100 250 500 1000 2000; do
  run_one SELECTOR "$GITHUB_WORKSPACE" perf/app-lam "$threshold" 60
  run_one SELECTOR "$GITHUB_WORKSPACE" perf/beta-ladder "$threshold" 60
  run_one SELECTOR "$GITHUB_WORKSPACE" con-leche "$threshold" 240
  run_one SELECTOR "$GITHUB_WORKSPACE" mathlib "$threshold" 240
done

python3 "$GITHUB_WORKSPACE/scripts/analyze_deep_boundary_v118.py" "$ROOT/report/results.txt" | tee "$ROOT/report/analysis.txt"
cp "$ROOT"/out/*.time "$ROOT/report/" || true
echo "V118_COMPLETE=PASS"
