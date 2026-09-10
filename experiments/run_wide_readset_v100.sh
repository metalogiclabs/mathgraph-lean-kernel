#!/usr/bin/env bash
set -euo pipefail
ARENA=92fba121dcd26902a0193c40485b3140af95e898
ROOT=/tmp/v100-wide
rm -rf "$ROOT" && mkdir -p "$ROOT/out"
echo "V100_HEAD=$(git rev-parse HEAD)"
cargo test --release --locked
RUSTFLAGS="-C target-cpu=native" cargo build --release --locked
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cd "$ROOT/arena"
nix develop -c ./lka.py build-test perf/beta-ladder >/dev/null
nix develop -c ./lka.py build-test con-leche >/dev/null
cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
cd "$GITHUB_WORKSPACE"
echo "V100_BETA_BEGIN"
/usr/bin/time -v target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/perf/beta-ladder.ndjson" >"$ROOT/out/beta.out" 2>"$ROOT/out/beta.err"
grep "Maximum resident set size" "$ROOT/out/beta.err" | sed "s/^/V100_BETA_/"
echo "V100_BETA=PASS"
echo "V100_CONLECHE_BEGIN"
start=$(date +%s)
set +e
/usr/bin/time -v target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/con-leche.ndjson" >"$ROOT/out/conleche.out" 2>"$ROOT/out/conleche.err" &
pid=$!
while kill -0 "$pid" 2>/dev/null; do
  elapsed=$(($(date +%s)-start))
  avail=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
  echo "V100_TELEMETRY elapsed_s=$elapsed mem_available_kb=$avail"
  sleep 5
done
wait "$pid"
rc=$?
set -e
echo "V100_CONLECHE_EXIT=$rc"
grep "Maximum resident set size" "$ROOT/out/conleche.err" | sed "s/^/V100_CONLECHE_/" || true
if [ "$rc" -eq 0 ]; then echo "V100_CONLECHE=PASS"; else echo "V100_CONLECHE=FAIL"; exit "$rc"; fi
