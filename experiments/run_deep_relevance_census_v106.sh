#!/usr/bin/env bash
set -euo pipefail

ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/deep-relevance-census-v106
rm -rf "$ROOT"
mkdir -p "$ROOT/out"

python3 scripts/apply_deep_relevance_census_v106.py
cargo test --release --locked -q

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
for t in perf/app-lam perf/beta-ladder perf/let-ladder perf/magma-list-deep-n36 con-leche mathlib; do
  echo "V106_BUILD_TEST=$t"
  nix develop -c ./lka.py build-test "$t" >/dev/null
done

cd "$GITHUB_WORKSPACE"
rm -rf pgo
RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$GITHUB_WORKSPACE/pgo" cargo build --release --locked -q
target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
cd "$ROOT/arena"
nix develop -c llvm-profdata merge -o "$GITHUB_WORKSPACE/pgo/merged.profdata" "$GITHUB_WORKSPACE/pgo"
cd "$GITHUB_WORKSPACE"
RUSTFLAGS="-C target-cpu=native -Cprofile-use=$GITHUB_WORKSPACE/pgo/merged.profdata" cargo build --release --locked -q

for t in perf/app-lam perf/beta-ladder perf/let-ladder perf/magma-list-deep-n36 con-leche mathlib; do
  safe="$(printf '%s' "$t" | tr '/' '_')"
  echo "V106_BEGIN=$t"
  MATHGRAPH_DEEP_CENSUS=1 target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" >"$ROOT/out/$safe.stdout" 2>"$ROOT/out/$safe.stderr"
  while IFS= read -r line; do
    printf 'V106_RESULT test=%s %s\n' "$t" "$line"
  done < <(grep 'V106_CENSUS' "$ROOT/out/$safe.stderr")
done
echo "V106_COMPLETE=PASS"
