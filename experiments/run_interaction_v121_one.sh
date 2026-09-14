#!/usr/bin/env bash
set -euo pipefail

: "${V121_MASK:?set V121_MASK}"

ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
SOURCE_RUN=34781716973
SOURCE_ARTIFACT=boundary-state-v117
ROOT="/tmp/interaction-v121-${V121_MASK}"
rm -rf "$ROOT"
mkdir -p "$ROOT/report" "$ROOT/v117"

echo "V121_HEAD=$(git rev-parse HEAD)"
echo "V121_MASK=$V121_MASK"
echo "V121_SOURCE_RUN=$SOURCE_RUN"

gh run download "$SOURCE_RUN" --repo metalogiclabs/mathgraph-lean-kernel -n "$SOURCE_ARTIFACT" -D "$ROOT/v117"
test -s "$ROOT/v117/ATLAS__mathlib.stderr"
test -s "$ROOT/v117/ATLAS__con-leche.stderr"
echo "V121_FROZEN_EVIDENCE=PASS"

python3 scripts/apply_causal_contraction_v120.py "$ROOT/v117"
cargo test --release --locked -q
echo "V121_SELECTOR_COMPILE=PASS"

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
nix develop -c ./lka.py build-test con-leche >/dev/null
echo "V121_BUILD_TEST=con-leche"

cd "$GITHUB_WORKSPACE"
rm -rf pgo
RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$GITHUB_WORKSPACE/pgo" cargo build --release --locked -q
env MATHGRAPH_V121_ABLATE_MASK=0 target/release/sokonanoda "$ROOT/config.json"   < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null 2>/dev/null
cd "$ROOT/arena"
nix develop -c llvm-profdata merge -o "$GITHUB_WORKSPACE/pgo/merged.profdata" "$GITHUB_WORKSPACE/pgo"
cd "$GITHUB_WORKSPACE"
RUSTFLAGS="-C target-cpu=native -Cprofile-use=$GITHUB_WORKSPACE/pgo/merged.profdata" cargo build --release --locked -q
echo "V121_PGO=PASS"

run_one () {
  local tag="$1"
  local mask="$2"
  local tf="$ROOT/${tag}.time"
  echo "V121_BEGIN tag=$tag mask=$mask"
  set +e
  env MATHGRAPH_V121_ABLATE_MASK="$mask"     /usr/bin/time -f 'wall=%e rss_kb=%M user=%U sys=%S' -o "$tf"     timeout 300 "$GITHUB_WORKSPACE/target/release/sokonanoda" "$ROOT/config.json"     < "$ROOT/arena/_build/tests/con-leche.ndjson" >"$ROOT/${tag}.stdout" 2>"$ROOT/${tag}.stderr"
  rc=$?
  set -e
  if [ -s "$tf" ]; then
    echo "V121_RESULT tag=$tag mask=$mask rc=$rc $(cat "$tf")" | tee -a "$ROOT/report/results.txt"
  else
    echo "V121_RESULT tag=$tag mask=$mask rc=$rc wall=300 rss_kb=0 user=0 sys=0" | tee -a "$ROOT/report/results.txt"
  fi
}

run_one CONTROL 0
run_one CANDIDATE "$V121_MASK"

cp "$ROOT"/*.time "$ROOT/report/" || true
echo "V121_COMPLETE=PASS"
