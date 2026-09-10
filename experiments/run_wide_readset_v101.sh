#!/usr/bin/env bash
set -euo pipefail
ARENA=92fba121dcd26902a0193c40485b3140af95e898
ROOT=/tmp/v101-quick
rm -rf "$ROOT" && mkdir -p "$ROOT/out"
echo "V101_HEAD=$(git rev-parse HEAD)"
cargo test --release --locked -q
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cd "$ROOT/arena"
for t in init-prelude perf/app-lam con-leche; do nix develop -c ./lka.py build-test "$t" >/dev/null; done
cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
cd "$GITHUB_WORKSPACE"
rm -rf pgo
RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$PWD/pgo" cargo build --release --locked -q
target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
cd "$ROOT/arena"
nix develop -c llvm-profdata merge -o "$GITHUB_WORKSPACE/pgo/merged.profdata" "$GITHUB_WORKSPACE/pgo"
cd "$GITHUB_WORKSPACE"
RUSTFLAGS="-C target-cpu=native -Cprofile-use=$PWD/pgo/merged.profdata" cargo build --release --locked -q
echo "V101_PGO_BUILD=PASS"
echo "V101_APPLAM_BEGIN"
/usr/bin/time -v timeout 30s target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/perf/app-lam.ndjson" >"$ROOT/out/app-lam.out" 2>"$ROOT/out/app-lam.err"
grep "Maximum resident set size" "$ROOT/out/app-lam.err" | sed "s/^/V101_APPLAM_/"
grep "Elapsed (wall clock) time" "$ROOT/out/app-lam.err" | sed "s/^/V101_APPLAM_/"
echo "V101_APPLAM=PASS"
echo "V101_CONLECHE_BEGIN"
start=$(date +%s)
set +e
/usr/bin/time -v target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/con-leche.ndjson" >"$ROOT/out/conleche.out" 2>"$ROOT/out/conleche.err" &
pid=$!
while kill -0 "$pid" 2>/dev/null; do
  elapsed=$(($(date +%s)-start))
  avail=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
  echo "V101_TELEMETRY elapsed_s=$elapsed mem_available_kb=$avail"
  sleep 5
done
wait "$pid"; rc=$?; set -e
echo "V101_CONLECHE_EXIT=$rc"
grep "Maximum resident set size" "$ROOT/out/conleche.err" | sed "s/^/V101_CONLECHE_/" || true
grep "Elapsed (wall clock) time" "$ROOT/out/conleche.err" | sed "s/^/V101_CONLECHE_/" || true
[ "$rc" -eq 0 ] || exit "$rc"
echo "V101_CONLECHE=PASS"
echo "V101_QUICK_GATE=PASS"
