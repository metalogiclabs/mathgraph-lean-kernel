#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
ROOT=/tmp/v83
mkdir -p "$ROOT/out"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
cd "$ROOT/base"
test "$(git rev-parse HEAD)" = "$BASE"
export RUSTFLAGS='-C target-cpu=x86-64 -C target-feature=-avx,-avx2,-avx512f,-fma -C debuginfo=1'
cargo build --release --locked -q
set +e
cargo test --locked -- --nocapture > "$ROOT/out/baseline-tests.log" 2>&1
test_rc=$?
set -e
printf '%s\n' "$test_rc" > "$ROOT/out/baseline-tests.rc"
echo "V83_BASELINE_TEST_RC=$test_rc"
cp target/release/sokonanoda "$ROOT/checker"
git diff --exit-code
cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}
EOF
valgrind --version | tee "$ROOT/out/valgrind-version.txt"
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
echo "V83_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)"
cd "$ROOT/arena"
for corpus in std cedar mathlib; do nix develop -c ./lka.py build-test "$corpus" >/dev/null; done
python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys,hashlib
r=Path(sys.argv[1]); limits={'std':2000,'cedar':2000,'mathlib':5000}
for c,n in limits.items():
    src=r/'arena'/'_build'/'tests'/f'{c}.ndjson'; dst=r/'out'/f'{c}.prefix.ndjson'
    with src.open('rb') as f,dst.open('wb') as o:
        for _ in range(n):
            line=f.readline()
            if not line: break
            o.write(line)
    assert dst.stat().st_size>0
    print(f'V83_{c.upper()}_PREFIX_SHA256={hashlib.sha256(dst.read_bytes()).hexdigest()}')
PY
cd "$ROOT"
for corpus in std cedar mathlib; do
  "$ROOT/checker" "$ROOT/config.json" < "$ROOT/out/$corpus.prefix.ndjson" > "$ROOT/out/$corpus.reference.out" 2> "$ROOT/out/$corpus.reference.err"
  echo "V83_${corpus^^}_REFERENCE=PASS"
done
profile_failed=0
for corpus in std cedar mathlib; do
  set +e
  timeout 600s valgrind --tool=callgrind --separate-threads=yes --callgrind-out-file="$ROOT/out/$corpus.callgrind" --dump-instr=yes --collect-jumps=no "$ROOT/checker" "$ROOT/config.json" < "$ROOT/out/$corpus.prefix.ndjson" > "$ROOT/out/$corpus.profile.out" 2> "$ROOT/out/$corpus.profile.err"
  rc=$?
  set -e
  if [ "$rc" -eq 0 ]; then
    cmp "$ROOT/out/$corpus.reference.out" "$ROOT/out/$corpus.profile.out"
    cmp "$ROOT/out/$corpus.reference.err" "$ROOT/out/$corpus.profile.err" >/dev/null 2>&1 || true
    echo "V83_${corpus^^}_PROFILE=COMPLETE_EXACT_STDOUT"
  else
    profile_failed=1
    echo "V83_${corpus^^}_PROFILE=INCOMPLETE_RC_$rc"
  fi
done
if [ "$profile_failed" -eq 0 ]; then
  python3 "$GITHUB_WORKSPACE/experiments/analyze_callgrind_v83.py" "$ROOT" | tee "$ROOT/summary.txt"
else
  echo 'DECISION=INCOMPLETE_PROFILE__NO_REPAIR_PROMOTED' | tee "$ROOT/summary.txt"
fi
if [ "$test_rc" -ne 0 ]; then
  echo 'V83_FINAL=BASELINE_TEST_FAILURE_RETAINED'
  exit "$test_rc"
fi
if [ "$profile_failed" -ne 0 ]; then exit 1; fi
