#!/usr/bin/env bash
set -euo pipefail

CURRENT=08ddb26718c86213262943ca19ae8cf1b03fa922
UPSTREAM=ceaabb593e830dd318bfefd1675be3142fad8eb7
COMPACT=c54878290f5aacf57b540ce27dab388106250a7d
ARENA=92fba121dcd26902a0193c40485b3140af95e898
VARIANT=${V99_VARIANT:-current}
ROOT="/tmp/v99-phase-${VARIANT}"
rm -rf "$ROOT" && mkdir -p "$ROOT/out"

case "$VARIANT" in
  current)
    REPO=https://github.com/metalogiclabs/mathgraph-lean-kernel
    REV=$CURRENT
    ;;
  upstream)
    REPO=https://github.com/intgrah/sokonanoda
    REV=$UPSTREAM
    ;;
  compact)
    REPO=https://github.com/metalogiclabs/mathgraph-lean-kernel
    REV=$COMPACT
    ;;
  *)
    echo "unknown V99_VARIANT=$VARIANT" >&2
    exit 2
    ;;
esac

echo "V99_PHASE_VARIANT=$VARIANT"
echo "V99_PHASE_REV=$REV"
echo "V99_PHASE_ARENA=$ARENA"
grep -E "MemTotal|SwapTotal" /proc/meminfo | sed "s/^/V99_HOST_/"

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cd "$ROOT/arena"
nix develop -c ./lka.py build-test con-leche >/dev/null
input=$(find "$ROOT/arena/_build/tests" -name con-leche.ndjson -print -quit)
test -n "$input"
echo "V99_PHASE_INPUT_BYTES=$(stat -c %s "$input")"

git clone -q "$REPO" "$ROOT/checker"
git -C "$ROOT/checker" checkout -q "$REV"
cd "$ROOT/checker"
RUSTFLAGS="-C target-cpu=native" cargo build --release --locked -q

cat >"$ROOT/check.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}
EOF

echo "V99_PHASE_BEGIN=$VARIANT:serial"
start=$(date +%s)
set +e
/usr/bin/time -v "$ROOT/checker/target/release/sokonanoda" "$ROOT/check.json" < "$input" >"$ROOT/out/check.out" 2>"$ROOT/out/check.err" &
pid=$!
while kill -0 "$pid" 2>/dev/null; do
  now=$(date +%s)
  elapsed=$((now-start))
  rss=$(awk '/VmRSS:/ {print $2}' "/proc/$pid/status" 2>/dev/null || echo 0)
  avail=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
  echo "V99_TELEMETRY variant=$VARIANT elapsed_s=$elapsed rss_kb=$rss mem_available_kb=$avail"
  sleep 5
done
wait "$pid"
rc=$?
set -e

rss=$(grep "Maximum resident set size" "$ROOT/out/check.err" | tail -1 | awk '{print $6}' || true)
elapsed=$(grep "Elapsed (wall clock) time" "$ROOT/out/check.err" | tail -1 | sed 's/.*: //' || true)
echo "V99_PHASE_${VARIANT}_EXIT=$rc"
echo "V99_PHASE_${VARIANT}_MAX_RSS_KB=${rss:-unknown}"
echo "V99_PHASE_${VARIANT}_ELAPSED=${elapsed:-unknown}"

python3 - "$ROOT" "$VARIANT" "$REV" "$rc" "${rss:-}" <<'PY'
import json, pathlib, sys
root=pathlib.Path(sys.argv[1])
variant, rev, rc, rss=sys.argv[2],sys.argv[3],int(sys.argv[4]),sys.argv[5]
(root/'phase.json').write_text(json.dumps({'variant':variant,'rev':rev,'exit':rc,'max_rss_kb':int(rss) if rss.isdigit() else None},indent=2))
PY

if [ "$rc" -eq 0 ]; then
  echo "V99_PHASE_RESULT=$VARIANT:PASS"
else
  echo "V99_PHASE_RESULT=$VARIANT:FAIL"
fi
exit "$rc"
