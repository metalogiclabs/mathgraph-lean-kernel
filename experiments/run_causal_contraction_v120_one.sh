#!/usr/bin/env bash
set -euo pipefail

: "${V120_GROUP:?set V120_GROUP}"

BASE=d6a73279e6765e637f9741180cefbd7ef957d8e5
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
SOURCE_RUN=34781716973
SOURCE_ARTIFACT=boundary-state-v117
ROOT="/tmp/causal-contraction-v120-${V120_GROUP}"
rm -rf "$ROOT"
mkdir -p "$ROOT/report" "$ROOT/v117"

echo "V120_HEAD=$(git rev-parse HEAD)"
echo "V120_GROUP=$V120_GROUP"
echo "V120_SOURCE_RUN=$SOURCE_RUN"

gh run download "$SOURCE_RUN" --repo metalogiclabs/mathgraph-lean-kernel -n "$SOURCE_ARTIFACT" -D "$ROOT/v117"
test -s "$ROOT/v117/ATLAS__mathlib.stderr"
test -s "$ROOT/v117/ATLAS__con-leche.stderr"
echo "V120_FROZEN_EVIDENCE=PASS"

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"

python3 scripts/apply_causal_contraction_v120.py "$ROOT/v117"
cargo test --release --locked -q
echo "V120_SELECTOR_COMPILE=PASS"

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
nix develop -c ./lka.py build-test con-leche >/dev/null
echo "V120_BUILD_TEST=con-leche"

build_pgo () {
  local dir="$1"
  local tag="$2"
  cd "$dir"
  rm -rf pgo
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$dir/pgo" cargo build --release --locked -q
  env MATHGRAPH_V120_ABLATE_GROUP=255 target/release/sokonanoda "$ROOT/config.json" \
    < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null 2>/dev/null
  cd "$ROOT/arena"
  nix develop -c llvm-profdata merge -o "$dir/pgo/merged.profdata" "$dir/pgo"
  cd "$dir"
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=$dir/pgo/merged.profdata" cargo build --release --locked -q
  echo "V120_PGO_$tag=PASS"
}

build_pgo "$ROOT/base" BASE
build_pgo "$GITHUB_WORKSPACE" CANDIDATE

run_one () {
  local tag="$1"
  local dir="$2"
  local group="$3"
  local tf="$ROOT/${tag}.time"
  echo "V120_BEGIN tag=$tag group=$group"
  set +e
  env MATHGRAPH_V120_ABLATE_GROUP="$group" \
    /usr/bin/time -f 'wall=%e rss_kb=%M user=%U sys=%S' -o "$tf" \
    timeout 300 "$dir/target/release/sokonanoda" "$ROOT/config.json" \
    < "$ROOT/arena/_build/tests/con-leche.ndjson" >"$ROOT/${tag}.stdout" 2>"$ROOT/${tag}.stderr"
  rc=$?
  set -e
  if [ -s "$tf" ]; then
    echo "V120_RESULT tag=$tag group=$group rc=$rc $(cat "$tf")" | tee -a "$ROOT/report/results.txt"
  else
    echo "V120_RESULT tag=$tag group=$group rc=$rc wall=300 rss_kb=0 user=0 sys=0" | tee -a "$ROOT/report/results.txt"
  fi
}

run_one BASE "$ROOT/base" 255
run_one CANDIDATE "$GITHUB_WORKSPACE" "$V120_GROUP"

cp "$ROOT"/*.time "$ROOT/report/" || true
echo "V120_COMPLETE=PASS"
