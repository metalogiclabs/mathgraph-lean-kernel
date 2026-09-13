#!/usr/bin/env bash
set -euo pipefail

BASE=d6a73279e6765e637f9741180cefbd7ef957d8e5
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/boundary-state-v117
rm -rf "$ROOT"
mkdir -p "$ROOT/out" "$ROOT/report"

echo "V117_HEAD=$(git rev-parse HEAD)"
echo "V117_BASE=$BASE"
echo "V117_ARENA=$ARENA"

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"

python3 scripts/apply_boundary_state_v117.py
cargo test --release --locked -q
echo "V117_BOUNDARY_COMPILE=PASS"

cp -a "$GITHUB_WORKSPACE" "$ROOT/atlas"
cd "$ROOT/atlas"
python3 scripts/apply_boundary_atlas_v117.py
cargo build --release --locked -q
echo "V117_ATLAS_COMPILE=PASS"

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
for t in mathlib con-leche perf/beta-ladder; do
  echo "V117_BUILD_TEST=$t"
  nix develop -c ./lka.py build-test "$t" >/dev/null
done

build_pgo () {
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
  echo "V117_PGO_$tag=PASS"
}

build_pgo "$ROOT/base" BASE
build_pgo "$GITHUB_WORKSPACE" BOUNDARY

run_one () {
  local tag="$1"
  local dir="$2"
  local test="$3"
  local timeout_s="$4"
  local safe
  safe="$(printf '%s' "$test" | tr '/' '_')"
  local out="$ROOT/out/${tag}__${safe}"
  echo "V117_BEGIN tag=$tag test=$test"
  set +e
  /usr/bin/time -f 'wall=%e rss_kb=%M user=%U sys=%S' -o "$out.time" \
    timeout "$timeout_s" "$dir/target/release/sokonanoda" "$ROOT/config.json" \
    < "$ROOT/arena/_build/tests/$test.ndjson" >"$out.stdout" 2>"$out.stderr"
  rc=$?
  set -e
  echo "V117_RESULT tag=$tag test=$test rc=$rc $(cat "$out.time")"
  return "$rc"
}

for t in perf/beta-ladder con-leche mathlib; do
  timeout_s=900
  [ "$t" = "con-leche" ] && timeout_s=1800
  [ "$t" = "mathlib" ] && timeout_s=3600
  run_one BASE "$ROOT/base" "$t" "$timeout_s"
  run_one BOUNDARY "$GITHUB_WORKSPACE" "$t" "$timeout_s"
done

cd "$ROOT/atlas"
for t in mathlib con-leche; do
  safe="$(printf '%s' "$t" | tr '/' '_')"
  echo "V117_ATLAS_BEGIN=$t"
  env MATHGRAPH_V117_ATLAS=1 target/release/sokonanoda "$ROOT/config.json" \
    < "$ROOT/arena/_build/tests/$t.ndjson" >"$ROOT/out/ATLAS__${safe}.stdout" 2>"$ROOT/out/ATLAS__${safe}.stderr"
done

python3 "$GITHUB_WORKSPACE/scripts/analyze_boundary_v117.py" "$ROOT/report/v117_report.json" \
  mathlib="$ROOT/out/ATLAS__mathlib.stderr" \
  con-leche="$ROOT/out/ATLAS__con-leche.stderr"

cp "$ROOT"/out/*.time "$ROOT/report/" || true
cp "$ROOT"/out/ATLAS__*.stderr "$ROOT/report/" || true
echo "V117_COMPLETE=PASS"
