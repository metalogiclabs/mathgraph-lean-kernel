#!/usr/bin/env bash
set -euo pipefail

: "${V118_WORKLOAD:?set V118_WORKLOAD}"
: "${V118_THRESHOLD:?set V118_THRESHOLD}"

BASE=d6a73279e6765e637f9741180cefbd7ef957d8e5
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
SAFE_WORKLOAD="$(printf '%s' "$V118_WORKLOAD" | tr '/' '_')"
ROOT="/tmp/deep-boundary-v118c-${SAFE_WORKLOAD}-${V118_THRESHOLD}"
rm -rf "$ROOT"
mkdir -p "$ROOT/report"

echo "V118C_HEAD=$(git rev-parse HEAD)"
echo "V118C_WORKLOAD=$V118_WORKLOAD"
echo "V118C_THRESHOLD=$V118_THRESHOLD"

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"

python3 scripts/apply_deep_boundary_selector_v118.py
cargo test --release --locked -q
echo "V118C_SELECTOR_COMPILE=PASS"

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
echo "V118C_BUILD_TEST=$V118_WORKLOAD"
nix develop -c ./lka.py build-test "$V118_WORKLOAD" >/dev/null

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
  echo "V118C_PGO_$tag=PASS"
}

build_pgo "$ROOT/base" BASE
build_pgo "$GITHUB_WORKSPACE" SELECTOR

run_one () {
  local tag="$1"
  local dir="$2"
  local threshold="$3"
  local timeout_s="$4"
  local timefile="$ROOT/${tag}.time"
  echo "V118C_BEGIN tag=$tag test=$V118_WORKLOAD threshold=$threshold"
  set +e
  env MATHGRAPH_V118_THRESHOLD_MILLI="$threshold" \
    /usr/bin/time -f 'wall=%e rss_kb=%M user=%U sys=%S' -o "$timefile" \
    timeout "$timeout_s" "$dir/target/release/sokonanoda" "$ROOT/config.json" \
    < "$ROOT/arena/_build/tests/$V118_WORKLOAD.ndjson" >"$ROOT/${tag}.stdout" 2>"$ROOT/${tag}.stderr"
  rc=$?
  set -e
  if [ -s "$timefile" ]; then
    echo "V118C_RESULT tag=$tag test=$V118_WORKLOAD threshold=$threshold rc=$rc $(cat "$timefile")" | tee -a "$ROOT/report/results.txt"
  else
    echo "V118C_RESULT tag=$tag test=$V118_WORKLOAD threshold=$threshold rc=$rc wall=$timeout_s rss_kb=0 user=0 sys=0" | tee -a "$ROOT/report/results.txt"
  fi
}

# One fresh job per workload/policy, so CI lifetime cannot masquerade as a policy failure.
run_one BASE "$ROOT/base" 0 300
run_one SELECTOR "$GITHUB_WORKSPACE" "$V118_THRESHOLD" 300

cp "$ROOT"/*.time "$ROOT/report/" || true
echo "V118C_COMPLETE=PASS"
