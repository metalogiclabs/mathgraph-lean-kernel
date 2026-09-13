#!/usr/bin/env bash
set -euo pipefail
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/wide-path-census-v112
rm -rf "$ROOT"
mkdir -p "$ROOT/out"

python3 scripts/apply_wide_path_census_v112.py
cargo test --release --locked -q

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
for t in mathlib con-leche; do
  echo "V112_BUILD_TEST=$t"
  nix develop -c ./lka.py build-test "$t" >/dev/null
done

cd "$GITHUB_WORKSPACE"
rm -rf pgo
RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$PWD/pgo" cargo build --release --locked -q
target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
cd "$ROOT/arena"
nix develop -c llvm-profdata merge -o "$GITHUB_WORKSPACE/pgo/merged.profdata" "$GITHUB_WORKSPACE/pgo"
cd "$GITHUB_WORKSPACE"
RUSTFLAGS="-C target-cpu=native -Cprofile-use=$PWD/pgo/merged.profdata" cargo build --release --locked -q

for t in mathlib con-leche; do
  safe="$(printf '%s' "$t" | tr '/' '_')"
  echo "V112_BEGIN=$t"
  /usr/bin/time -f 'V112_TIME wall=%e rss_kb=%M'     env MATHGRAPH_V112_CENSUS=1 target/release/sokonanoda "$ROOT/config.json"     < "$ROOT/arena/_build/tests/$t.ndjson"     > "$ROOT/out/$safe.stdout" 2> "$ROOT/out/$safe.stderr"
  grep -E 'V112_CENSUS|V112_TIME' "$ROOT/out/$safe.stderr" | sed "s#^#V112_RESULT test=$t #"
done

echo "V112_COMPLETE=PASS"
