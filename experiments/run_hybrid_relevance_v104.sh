#!/usr/bin/env bash
set -euo pipefail

ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
BASE=611f607a6cf6150fd341330cfcfcedd7a4b4453f
ROOT=/tmp/hybrid-relevance-v104
rm -rf "$ROOT"
mkdir -p "$ROOT/out"

echo "V104_HEAD=$(git rev-parse HEAD)"
echo "V104_BASE=$BASE"
echo "V104_ARENA=$ARENA"
grep -E "MemTotal|SwapTotal" /proc/meminfo | sed 's/^/V104_HOST_/'

cargo test --release --locked -q
echo "V104_RUST_TESTS=PASS"

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
for t in perf/app-lam perf/beta-ladder perf/let-ladder perf/shift-cascade perf/magma-list-deep-n36 con-leche mathlib; do
  echo "V104_BUILD_TEST=$t"
  nix develop -c ./lka.py build-test "$t" >/dev/null
done

build_pgo () {
  local dir="$1"
  local tag="$2"
  cd "$dir"
  rm -rf pgo
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$dir/pgo" cargo build --release --locked -q
  target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
  cd "$ROOT/arena"
  nix develop -c llvm-profdata merge -o "$dir/pgo/merged.profdata" "$dir/pgo"
  cd "$dir"
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=$dir/pgo/merged.profdata" cargo build --release --locked -q
  echo "V104_PGO_$tag=PASS"
}

build_pgo "$ROOT/base" V102
build_pgo "$GITHUB_WORKSPACE" V104

PERF_OK=0
if command -v perf >/dev/null 2>&1; then
  sudo sysctl -w kernel.perf_event_paranoid=-1 >/dev/null 2>&1 || true
  perf stat -x, -e instructions -o "$ROOT/perf-probe.csv" -- true >/dev/null 2>&1 || true
  if grep -Eq '^[0-9]+,.*instructions' "$ROOT/perf-probe.csv" 2>/dev/null; then
    PERF_OK=1
  fi
fi
echo "V104_PERF_OK=$PERF_OK"
cat "$ROOT/perf-probe.csv" 2>/dev/null || true

run_one () {
  local tag="$1"
  local bin="$2"
  local test="$3"
  local timeout_s="$4"
  local safe="$(printf '%s' "$test" | tr '/' '_')"
  local out="$ROOT/out/${tag}__${safe}"
  local in="$ROOT/arena/_build/tests/$test.ndjson"
  echo "V104_BEGIN tag=$tag test=$test"
  set +e
  if [ "$PERF_OK" -eq 1 ]; then
    timeout "$timeout_s" perf stat -x, -e instructions -o "$out.perf" -- /usr/bin/time -v "$bin" "$ROOT/config.json" < "$in" >"$out.stdout" 2>"$out.time"
    rc=$?
  else
    timeout "$timeout_s" /usr/bin/time -v "$bin" "$ROOT/config.json" < "$in" >"$out.stdout" 2>"$out.time"
    rc=$?
  fi
  set -e
  wall=$(grep -F "Elapsed (wall clock) time" "$out.time" | sed 's/.*: //' | tail -1)
  rss=$(grep -F "Maximum resident set size" "$out.time" | awk '{print $NF}' | tail -1)
  instr=""
  if [ -f "$out.perf" ]; then
    instr=$(awk -F, '$3=="instructions"{gsub(/ /,"",$1);print $1}' "$out.perf" | tail -1)
  fi
  echo "V104_RESULT tag=$tag test=$test rc=$rc wall=$wall rss_kb=$rss instructions=$instr"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$tag" "$test" "$rc" "$wall" "$rss" "$instr" >> "$ROOT/results.tsv"
  return "$rc"
}

: > "$ROOT/results.tsv"
for t in perf/app-lam perf/beta-ladder perf/let-ladder perf/shift-cascade perf/magma-list-deep-n36; do
  run_one V102 "$ROOT/base/target/release/sokonanoda" "$t" 600
  run_one V104 "$GITHUB_WORKSPACE/target/release/sokonanoda" "$t" 600
done
run_one V102 "$ROOT/base/target/release/sokonanoda" con-leche 1800
run_one V104 "$GITHUB_WORKSPACE/target/release/sokonanoda" con-leche 1800
run_one V102 "$ROOT/base/target/release/sokonanoda" mathlib 3600
run_one V104 "$GITHUB_WORKSPACE/target/release/sokonanoda" mathlib 3600

python3 - "$ROOT/results.tsv" <<'PY'
import sys
rows=[]
for line in open(sys.argv[1]):
    tag,test,rc,wall,rss,instr=line.rstrip("\n").split("\t")
    rows.append(dict(tag=tag,test=test,rc=int(rc),wall=wall,rss_kb=int(rss or 0),instructions=instr))
by={}
for r in rows:
    by.setdefault(r["test"],{})[r["tag"]]=r
print("V104_SUMMARY_BEGIN")
for t,p in by.items():
    a,b=p["V102"],p["V104"]
    rss_delta=(b["rss_kb"]-a["rss_kb"])/a["rss_kb"]*100 if a["rss_kb"] else 0
    print(f"{t}: v102_wall={a['wall']} v104_wall={b['wall']} v102_rss={a['rss_kb']} v104_rss={b['rss_kb']} rss_delta_pct={rss_delta:.2f} v102_instr={a['instructions']} v104_instr={b['instructions']}")
print("V104_SUMMARY_END")
PY

echo "V104_COMPLETE=PASS"
