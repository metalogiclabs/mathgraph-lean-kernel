#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ROOT=/tmp/v81
rm -rf "$ROOT" && mkdir -p "$ROOT/out"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
cd "$ROOT/base"
test "$(git rev-parse HEAD)" = "$BASE"
RUSTFLAGS='-C target-cpu=native -C debuginfo=1' cargo build --release --locked -q
# Record the complete unmodified baseline test result. A failing test is not waived.
set +e
cargo test --locked -- --nocapture > "$ROOT/out/baseline-tests.log" 2>&1
test_rc=$?
set -e
printf '%s\n' "$test_rc" > "$ROOT/out/baseline-tests.rc"
cat "$ROOT/out/baseline-tests.log"
echo "V81_BASELINE_TEST_RC=$test_rc"
cp target/release/sokonanoda "$ROOT/checker"
git diff --exit-code
cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}
EOF
command -v valgrind >/dev/null
command -v callgrind_annotate >/dev/null
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
echo "V81_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)"
cd "$ROOT/arena"
for corpus in std cedar mathlib; do nix develop -c ./lka.py build-test "$corpus" >/dev/null; done
cd "$ROOT"
python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
r=Path(sys.argv[1]); limits={'std':2000,'cedar':2000,'mathlib':5000}
for c,n in limits.items():
    src=r/'arena'/'_build'/'tests'/f'{c}.ndjson'
    with src.open('rb') as f, (r/'out'/f'{c}.prefix.ndjson').open('wb') as o:
        for _ in range(n):
            line=f.readline()
            if not line: break
            o.write(line)
    assert (r/'out'/f'{c}.prefix.ndjson').stat().st_size>0
    print(f'V81_{c.upper()}_PREFIX_LINES={sum(1 for _ in (r/"out"/f"{c}.prefix.ndjson").open("rb"))}')
PY
for corpus in std cedar mathlib; do
  "$ROOT/checker" "$ROOT/config.json" < "$ROOT/out/$corpus.prefix.ndjson" > "$ROOT/out/$corpus.reference.out" 2> "$ROOT/out/$corpus.reference.err"
  echo "V81_${corpus^^}_PREFIX_REFERENCE=PASS"
done
for corpus in std cedar mathlib; do
  set +e
  timeout 600s valgrind --tool=callgrind --callgrind-out-file="$ROOT/out/$corpus.callgrind" --dump-instr=yes --collect-jumps=no --separate-threads=yes "$ROOT/checker" "$ROOT/config.json" < "$ROOT/out/$corpus.prefix.ndjson" > "$ROOT/out/$corpus.profile.out" 2> "$ROOT/out/$corpus.profile.err"
  rc=$?
  set -e
  if [ "$rc" -eq 0 ]; then
    cmp "$ROOT/out/$corpus.reference.out" "$ROOT/out/$corpus.profile.out"
    callgrind_annotate --inclusive=yes --threshold=0.1 "$ROOT/out/$corpus.callgrind" > "$ROOT/out/$corpus.annotated.txt"
    echo "V81_${corpus^^}_PROFILE=COMPLETE_EXACT"
  else
    echo "V81_${corpus^^}_PROFILE=INCOMPLETE_RC_$rc"
  fi
done
python3 - "$ROOT" <<'PY' | tee "$ROOT/summary.txt"
from pathlib import Path
import sys,re,json
r=Path(sys.argv[1]); out={}
test_rc=int((r/'out'/'baseline-tests.rc').read_text())
print(f'V81_BASELINE_TEST_RC={test_rc}')
for c in ('std','cedar','mathlib'):
    p=r/'out'/f'{c}.annotated.txt'
    if not p.exists():
        out[c]={'status':'INCOMPLETE'}; print(f'V81_{c.upper()}_COST=UNKNOWN'); continue
    text=p.read_text(errors='replace')
    rows=[]
    for line in text.splitlines():
        if re.search(r'force_all|eval_no_cache|key_env|prune_env|intern_frame|store_lookup|global_key|infer_value|conv_types',line):
            rows.append(line.strip())
    out[c]={'status':'COMPLETE','matching_rows':rows}
    print(f'V81_{c.upper()}_COST_PROFILE=COMPLETE')
    for line in rows[:50]: print(f'V81_{c.upper()}_COST_ROW {line}')
(r/'cost-profile.json').write_text(json.dumps(out,indent=2))
print('DECISION=DIAGNOSTIC_ONLY__NO_REPAIR_PROMOTED' if test_rc else 'DECISION=UNINSTRUMENTED_COST_PROFILE__NO_REPAIR_PROMOTED')
print('RULE=USE_REACHABILITY_AND_MEASURED_COST_TO_SELECT_ONE_CAUSAL_REPAIR')
PY
# Preserve the failing safety gate even when independent profiling succeeds.
if [ "$test_rc" -ne 0 ]; then
  echo 'V81_FINAL=BASELINE_TEST_FAILURE_RETAINED__DIAGNOSTIC_ONLY'
  exit "$test_rc"
fi
