#!/usr/bin/env bash
set -euo pipefail
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/sparse-scoreboard-census-v111b
rm -rf "$ROOT"
mkdir -p "$ROOT/out"

python3 scripts/apply_bounded_sparse_v105.py
python3 scripts/apply_sparse_admission_census_v107.py
cargo test --release --locked -q
cargo build --release --locked -q

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
for t in mathlib cedar perf/magma-list-deep-n36 perf/magma-list-pair-n21; do
  echo "V111B_BUILD_TEST=$t"
  nix develop -c ./lka.py build-test "$t" >/dev/null
done

cd "$GITHUB_WORKSPACE"
for t in mathlib cedar perf/magma-list-deep-n36 perf/magma-list-pair-n21; do
  safe="$(printf '%s' "$t" | tr '/' '_')"
  echo "V111B_BEGIN=$t"
  /usr/bin/time -f 'V111B_TIME wall=%e rss_kb=%M'     env MATHGRAPH_V107_CENSUS=1 target/release/sokonanoda "$ROOT/config.json"     < "$ROOT/arena/_build/tests/$t.ndjson"     > "$ROOT/out/$safe.stdout" 2> "$ROOT/out/$safe.stderr"
  grep -E 'V107_CENSUS|V111B_TIME' "$ROOT/out/$safe.stderr" | sed "s#^#V111B_RESULT test=$t #"
done

echo "V111B_COMPLETE=PASS"
