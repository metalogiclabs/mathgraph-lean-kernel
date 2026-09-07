#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
ROOT=/tmp/v82
mkdir -p "$ROOT/out"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
cd "$ROOT/base"
test "$(git rev-parse HEAD)" = "$BASE"
# A portable diagnostic build, not the native Arena performance binary.
# Explicitly disable newer SIMD to avoid Valgrind's unsupported-instruction path.
export RUSTFLAGS='-C target-cpu=x86-64 -C target-feature=-avx,-avx2,-avx512f,-fma -C debuginfo=1'
cargo build --release --locked -q
set +e
cargo test --locked -- --nocapture > "$ROOT/out/baseline-tests.log" 2>&1
test_rc=$?
set -e
printf '%s\n' "$test_rc" > "$ROOT/out/baseline-tests.rc"
echo "V82_BASELINE_TEST_RC=$test_rc"
cp target/release/sokonanoda "$ROOT/checker"
git diff --exit-code
cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}
EOF
valgrind --version | tee "$ROOT/out/valgrind-version.txt"
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
echo "V82_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)"
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
    print(f'V82_{c.upper()}_PREFIX_SHA256={hashlib.sha256(dst.read_bytes()).hexdigest()}')
PY
cd "$ROOT"
for corpus in std cedar mathlib; do
  "$ROOT/checker" "$ROOT/config.json" < "$ROOT/out/$corpus.prefix.ndjson" > "$ROOT/out/$corpus.reference.out" 2> "$ROOT/out/$corpus.reference.err"
  echo "V82_${corpus^^}_REFERENCE=PASS"
done
for corpus in std cedar mathlib; do
  set +e
  timeout 600s valgrind --tool=callgrind --callgrind-out-file="$ROOT/out/$corpus.callgrind" --dump-instr=yes --collect-jumps=no "$ROOT/checker" "$ROOT/config.json" < "$ROOT/out/$corpus.prefix.ndjson" > "$ROOT/out/$corpus.profile.out" 2> "$ROOT/out/$corpus.profile.err"
  rc=$?
  set -e
  if [ "$rc" -eq 0 ]; then
    cmp "$ROOT/out/$corpus.reference.out" "$ROOT/out/$corpus.profile.out"
    callgrind_annotate --inclusive=yes --threshold=0.1 "$ROOT/out/$corpus.callgrind" > "$ROOT/out/$corpus.annotated.txt"
    echo "V82_${corpus^^}_PROFILE=COMPLETE_EXACT"
  else
    echo "V82_${corpus^^}_PROFILE=INCOMPLETE_RC_$rc"
  fi
done
python3 - "$ROOT" <<'PY' | tee "$ROOT/summary.txt"
from pathlib import Path
import sys,re,json
r=Path(sys.argv[1]); out={}; test_rc=int((r/'out/baseline-tests.rc').read_text())
print(f'V82_BASELINE_TEST_RC={test_rc}')
for c in ('std','cedar','mathlib'):
    p=r/'out'/f'{c}.annotated.txt'
    if not p.exists():
        out[c]={'status':'INCOMPLETE'}; print(f'V82_{c.upper()}_COST=UNKNOWN'); continue
    rows=[s.strip() for s in p.read_text(errors='replace').splitlines() if re.search(r'force_all|eval_no_cache|key_env|prune_env|intern_frame|store_lookup|global_key|infer_value|conv_types',s)]
    out[c]={'status':'COMPLETE','matching_rows':rows}
    print(f'V82_{c.upper()}_COST_PROFILE=COMPLETE')
    for line in rows[:50]: print(f'V82_{c.upper()}_COST_ROW {line}')
(r/'cost-profile.json').write_text(json.dumps(out,indent=2))
print('DECISION=DIAGNOSTIC_ONLY__NO_REPAIR_PROMOTED')
print('RULE=PORTABLE_INSTRUCTION_COUNTS_ARE_NOT_NATIVE_CPU_TIME')
PY
# Do not turn missing negative fixtures into a green safety gate.
if [ "$test_rc" -ne 0 ]; then
  echo 'V82_FINAL=BASELINE_TEST_FAILURE_RETAINED'
  exit "$test_rc"
fi
