#!/usr/bin/env bash
set -euo pipefail
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/wide-activation-v116
rm -rf "$ROOT"
mkdir -p "$ROOT/out" "$ROOT/report"

python3 scripts/apply_wide_activation_atlas_v116.py
cargo test --release --locked -q
cargo build --release --locked -q

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
for t in mathlib con-leche; do
  echo "V116_BUILD_TEST=$t"
  nix develop -c ./lka.py build-test "$t" >/dev/null
done

cd "$GITHUB_WORKSPACE"
for t in mathlib con-leche; do
  safe="$(printf '%s' "$t" | tr '/' '_')"
  echo "V116_BEGIN=$t"
  env MATHGRAPH_V116_ATLAS=1 target/release/sokonanoda "$ROOT/config.json" \
    < "$ROOT/arena/_build/tests/$t.ndjson" >"$ROOT/out/$safe.stdout" 2>"$ROOT/out/$safe.stderr"
done

python3 scripts/analyze_wide_activation_v116.py "$ROOT/report/v116_report.json" \
  mathlib="$ROOT/out/mathlib.stderr" con-leche="$ROOT/out/con-leche.stderr"
cp "$ROOT"/out/*.stderr "$ROOT/report/"
echo "V116_RUN_COMPLETE=PASS"
