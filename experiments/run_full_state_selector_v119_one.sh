#!/usr/bin/env bash
set -euo pipefail

: "${V119_WORKLOAD:?set V119_WORKLOAD}"
: "${V119_THRESHOLD:?set V119_THRESHOLD}"

BASE=d6a73279e6765e637f9741180cefbd7ef957d8e5
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
SOURCE_RUN=34781716973
SOURCE_ARTIFACT=boundary-state-v117
SAFE_WORKLOAD="$(printf '%s' "$V119_WORKLOAD" | tr '/' '_')"
ROOT="/tmp/full-state-v119-${SAFE_WORKLOAD}-${V119_THRESHOLD}"
rm -rf "$ROOT"
mkdir -p "$ROOT/report" "$ROOT/v117"

echo "V119_HEAD=$(git rev-parse HEAD)"
echo "V119_WORKLOAD=$V119_WORKLOAD"
echo "V119_THRESHOLD=$V119_THRESHOLD"
echo "V119_SOURCE_RUN=$SOURCE_RUN"

gh run download "$SOURCE_RUN" --repo metalogiclabs/mathgraph-lean-kernel -n "$SOURCE_ARTIFACT" -D "$ROOT/v117"
test -s "$ROOT/v117/ATLAS__mathlib.stderr"
test -s "$ROOT/v117/ATLAS__con-leche.stderr"
echo "V119_FROZEN_EVIDENCE=PASS"

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"

python3 scripts/apply_full_state_selector_v119.py "$ROOT/v117"
cargo test --release --locked -q
echo "V119_SELECTOR_COMPILE=PASS"

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
echo "V119_BUILD_TEST=$V119_WORKLOAD"
nix develop -c ./lka.py build-test "$V119_WORKLOAD" >/dev/null

build_pgo () {
  local dir="$1"
  local tag="$2"
  cd "$dir"
  rm -rf pgo
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$dir/pgo" cargo build --release --locked -q
  env MATHGRAPH_V119_THRESHOLD_MILLI=0 target/release/sokonanoda "$ROOT/config.json" \
    < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null 2>/dev/null
  cd "$ROOT/arena"
  nix develop -c llvm-profdata merge -o "$dir/pgo/merged.profdata" "$dir/pgo"
  cd "$dir"
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=$dir/pgo/merged.profdata" cargo build --release --locked -q
  echo "V119_PGO_$tag=PASS"
}

build_pgo "$ROOT/base" BASE
build_pgo "$GITHUB_WORKSPACE" SELECTOR

run_one () {
  local tag="$1"
  local dir="$2"
  local threshold="$3"
  local timeout_s="$4"
  local tf="$ROOT/${tag}.time"
  echo "V119_BEGIN tag=$tag test=$V119_WORKLOAD threshold=$threshold"
  set +e
  env MATHGRAPH_V119_THRESHOLD_MILLI="$threshold" \
    /usr/bin/time -f 'wall=%e rss_kb=%M user=%U sys=%S' -o "$tf" \
    timeout "$timeout_s" "$dir/target/release/sokonanoda" "$ROOT/config.json" \
    < "$ROOT/arena/_build/tests/$V119_WORKLOAD.ndjson" >"$ROOT/${tag}.stdout" 2>"$ROOT/${tag}.stderr"
  rc=$?
  set -e
  if [ -s "$tf" ]; then
    echo "V119_RESULT tag=$tag test=$V119_WORKLOAD threshold=$threshold rc=$rc $(cat "$tf")" | tee -a "$ROOT/report/results.txt"
  else
    echo "V119_RESULT tag=$tag test=$V119_WORKLOAD threshold=$threshold rc=$rc wall=$timeout_s rss_kb=0 user=0 sys=0" | tee -a "$ROOT/report/results.txt"
  fi
}

run_one BASE "$ROOT/base" 0 300
run_one SELECTOR "$GITHUB_WORKSPACE" "$V119_THRESHOLD" 300

cp "$ROOT"/*.time "$ROOT/report/" || true
echo "V119_COMPLETE=PASS"
