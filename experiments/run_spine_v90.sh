#!/usr/bin/env bash
set -euo pipefail
MODE=${1:?preflight or benchmark required}
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
ROOT=/tmp/v90
OUT=$ROOT/out
SRC=$GITHUB_WORKSPACE/experiments
mkdir -p "$OUT"
export RUSTFLAGS='-C target-cpu=native'

prepare() {
  mkdir -p "$ROOT/control" "$ROOT/candidate"
  git -C "$GITHUB_WORKSPACE" fetch -q origin "$BASE"
  git -C "$GITHUB_WORKSPACE" archive "$BASE" | tar -x -C "$ROOT/control"
  cp -a "$ROOT/control/." "$ROOT/candidate/"
  python3 "$SRC/patch_spine_v90.py" "$ROOT/candidate" ${1:+--with-tests}
  diff -u "$ROOT/control/src/value.rs" "$ROOT/candidate/src/value.rs" > "$OUT/production.patch" || test "$?" -eq 1
  python3 - "$ROOT" "$SRC" <<'PY'
from pathlib import Path
import sys,json
r=Path(sys.argv[1]); a=(r/'control/src/value.rs').read_bytes(); b=(r/'candidate/src/value.rs').read_bytes()
sys.path.insert(0,sys.argv[2])
from patch_spine_v90 import BASE, OLD, NEW, blob
assert blob(a)==BASE
assert b.replace(NEW.encode(),OLD.encode())==a
assert blob((r/'control/src/eval.rs').read_bytes())=='c1c49a644c1475d6f433d32f553a70a1d5fb8f99'
assert blob((r/'candidate/src/eval.rs').read_bytes())=='c1c49a644c1475d6f433d32f553a70a1d5fb8f99'
(r/'out/source-evidence.json').write_text(json.dumps({'base':'08ddb26718c86213262943ca19ae8cf1b03fa922','control_value_blob':blob(a),'candidate_value_blob':blob(b),'source_ablation':'EXACT','production_change':'inline_spine_materialization_only','release_promoted':False},indent=2))
print('V90_EXACT_SOURCE_ABLATION=PASS')
PY
}

if [[ "$MODE" == preflight ]]; then
  prepare tests
  (cd "$ROOT/control" && PYTHONPATH="$SRC" python3 -m unittest -v test_patch_spine_v90) > "$OUT/patcher-tests.log" 2>&1
  echo 'V90_PATCHER_TESTS=PASS'
  for arm in control candidate; do
    export CARGO_TARGET_DIR="$ROOT/target-$arm"
    if [[ "$arm" == candidate ]]; then
      (cd "$ROOT/$arm" && cargo test --locked -- spine_v90) > "$OUT/candidate.focused.log" 2>&1
      grep -Eq 'test result: ok\. 2 passed; 0 failed;' "$OUT/candidate.focused.log"
    fi
    set +e
    (cd "$ROOT/$arm" && cargo test --locked) > "$OUT/$arm.tests.log" 2>&1
    rc=$?
    set -e
    printf '%s\n' "$rc" > "$OUT/$arm.tests.rc"
  done
  python3 - "$OUT" "$SRC" <<'PY'
import json,sys
from pathlib import Path
out=Path(sys.argv[1]);sys.path.insert(0,sys.argv[2])
from check_test_results_v88 import parse,EXPECTED
r={'release_qualified':False}
for arm,n in [('control',42),('candidate',44)]:
    q=parse((out/f'{arm}.tests.log').read_text(),n)
    q['rc']=int((out/f'{arm}.tests.rc').read_text())
    assert q['rc']==101 and set(q['failures'])==EXPECTED and q['passed']==n-2
    r[arm]=q
r['no_new_test_failures']=True
(out/'qualification.json').write_text(json.dumps(r,indent=2))
print('V90_NO_NEW_TEST_FAILURES=PASS')
print('V90_RELEASE_QUALIFICATION=BLOCKED_KNOWN_FIXTURES')
PY
  exit 0
fi

if [[ "$MODE" != benchmark ]]; then echo 'Unknown mode' >&2; exit 2; fi
prepare
command -v cargo >/dev/null
LLVM_FLAKE='github:NixOS/nixpkgs/0ad6f47ea4fe188f4bc8f0380f93ae8523337c6c#llvmPackages_21.llvm'
if [[ ! -d "$ROOT/arena/.git" ]]; then
  git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
fi
git -C "$ROOT/arena" checkout -q "$ARENA"
test "$(git -C "$ROOT/arena" rev-parse HEAD)" = "$ARENA"
(cd "$ROOT/arena" && for c in init-prelude cedar mathlib; do ./lka.py build-test "$c"; done)
cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
for arm in control candidate; do
  pgo="$ROOT/pgo-$arm"
  mkdir -p "$pgo"
  export CARGO_TARGET_DIR="$ROOT/target-$arm"
  export RUSTFLAGS="-C target-cpu=native -C profile-generate=$pgo"
  (cd "$ROOT/$arm" && cargo build --release --locked -q) > "$OUT/$arm.pgo-build.log" 2>&1
  "$CARGO_TARGET_DIR/release/sokonanoda" "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" > "$OUT/$arm.pgo.stdout" 2> "$OUT/$arm.pgo.stderr"
  nix shell "$LLVM_FLAKE" -c llvm-profdata merge -o "$pgo/merged.profdata" "$pgo"
  test -s "$pgo/merged.profdata"
  export RUSTFLAGS="-C target-cpu=native -C profile-use=$pgo/merged.profdata"
  (cd "$ROOT/$arm" && cargo build --release --locked -q) > "$OUT/$arm.release-build.log" 2>&1
  cp "$CARGO_TARGET_DIR/release/sokonanoda" "$ROOT/$arm-checker"
  echo "V90_${arm^^}_PGO_BUILD=PASS"
done
python3 "$SRC/measure_prune_dm_v88.py" "$ROOT"
python3 - "$OUT" <<'PY'
import json,sys
from pathlib import Path
out=Path(sys.argv[1]); d=json.loads((out/'results.json').read_text())
q=json.loads((out/'qualification.json').read_text())
assert q['no_new_test_failures'] and not q['release_qualified']
assert d['status']=='COMPLETE' and set(d['corpora'])=={'std','cedar','mathlib'}
record={'schema':1,'candidate':'inline-spine-v90','source_evidence':json.loads((out/'source-evidence.json').read_text()),'qualification':q,'benchmark':d,'decision':d['decision'],'release_promoted':False}
(out/'experiment.json').write_text(json.dumps(record,indent=2))
print('V90_EXPERIMENT_RECORD=PASS')
print('V90_DECISION='+d['decision']+'__NO_RELEASE_PROMOTION')
PY
