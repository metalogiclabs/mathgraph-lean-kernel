#!/usr/bin/env bash
set -euo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
ARENA=92fba121dcd26902a0193c40485b3140af95e898
ROOT=/tmp/v99-six
rm -rf "$ROOT" && mkdir -p "$ROOT/out"
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/checker"
git -C "$ROOT/checker" checkout -q "$BASE"
cat >"$ROOT/checker/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
cd "$ROOT/arena"
for t in perf/magma-list-pair-n7 perf/magma-list-pair-n21 perf/magma-list-deep-n21 perf/magma-list-deep-n36 perf/magma-string-n4 perf/magma-string-pair-n9; do
  nix develop -c ./lka.py build-test "$t" >/dev/null
done
cd "$ROOT/checker"
RUSTFLAGS="-C target-cpu=native" cargo build --release --locked -q
fails=0
for t in perf/magma-list-pair-n7 perf/magma-list-pair-n21 perf/magma-list-deep-n21 perf/magma-list-deep-n36 perf/magma-string-n4 perf/magma-string-pair-n9; do
  f="$ROOT/arena/_build/tests/$t.ndjson"
  echo "V99_SIX_BEGIN=$t"
  set +e
  target/release/sokonanoda config.json < "$f" >"$ROOT/out/$(basename "$t").out" 2>"$ROOT/out/$(basename "$t").err"
  rc=$?
  set -e
  echo "V99_SIX_EXIT_$t=$rc"
  if [ "$rc" -ne 0 ]; then fails=$((fails+1)); fi
done
echo "V99_SIX_FAILURES=$fails"
if [ "$fails" -eq 0 ]; then echo "V99_SIX_GATE=PASS"; else echo "V99_SIX_GATE=FAIL"; exit 1; fi
