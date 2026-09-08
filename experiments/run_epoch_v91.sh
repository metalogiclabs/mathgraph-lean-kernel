#!/usr/bin/env bash
set -euo pipefail
MODE=${1:?preflight or benchmark required}
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
ROOT=/tmp/v91
OUT=$ROOT/out
SRC=$GITHUB_WORKSPACE/experiments
mkdir -p "$OUT"
export RUSTFLAGS='-C target-cpu=native'
prepare() {
  rm -rf "$ROOT/control" "$ROOT/candidate"
  mkdir -p "$ROOT/control" "$ROOT/candidate"
  git -C "$GITHUB_WORKSPACE" fetch -q origin "$BASE"
  git -C "$GITHUB_WORKSPACE" archive "$BASE" | tar -x -C "$ROOT/control"
  cp -a "$ROOT/control/." "$ROOT/candidate/"
  python3 "$SRC/patch_epoch_v91.py" "$ROOT/candidate"
  diff -u "$ROOT/control/src/util.rs" "$ROOT/candidate/src/util.rs" > "$OUT/production.patch" || test "$?" -eq 1
  python3 - "$ROOT" "$SRC" <<'PY'
from pathlib import Path
import sys,json
r=Path(sys.argv[1]);sys.path.insert(0,sys.argv[2])
from patch_epoch_v91 import blob,BASE,CANDIDATE,transform
a=(r/'control/src/util.rs').read_bytes(); b=(r/'candidate/src/util.rs').read_bytes()
assert blob(a)==BASE and blob(b)==CANDIDATE
assert transform(a.decode()).encode()==b
assert (r/'control/src/eval.rs').read_bytes()==(r/'candidate/src/eval.rs').read_bytes()
(r/'out/source-evidence.json').write_text(json.dumps({'base':'08ddb26718c86213262943ca19ae8cf1b03fa922','control_util_blob':BASE,'candidate_util_blob':CANDIDATE,'source_transform':'DETERMINISTIC_EXACT','production_change':'epoch_invalidation_for_get_insert_caches','release_promoted':False},indent=2))
print('V91_EXACT_SOURCE_TRANSFORM=PASS')
PY
}
if [[ "$MODE" == preflight ]]; then
  prepare
  for arm in control candidate; do
    export CARGO_TARGET_DIR="$ROOT/target-$arm"
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
for arm in ('control','candidate'):
    q=parse((out/f'{arm}.tests.log').read_text(),42); q['rc']=int((out/f'{arm}.tests.rc').read_text())
    assert q['rc']==101 and set(q['failures'])==EXPECTED and q['passed']==40
    r[arm]=q
r['no_new_test_failures']=True
(out/'qualification.json').write_text(json.dumps(r,indent=2))
print('V91_NO_NEW_TEST_FAILURES=PASS')
print('V91_RELEASE_QUALIFICATION=BLOCKED_KNOWN_FIXTURES')
PY
  exit 0
fi
[[ "$MODE" == benchmark ]] || exit 2
prepare
LLVM_FLAKE='github:NixOS/nixpkgs/0ad6f47ea4fe188f4bc8f0380f93ae8523337c6c#llvmPackages_21.llvm'
if [[ ! -d "$ROOT/arena/.git" ]]; then git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"; fi
git -C "$ROOT/arena" checkout -q "$ARENA"
(cd "$ROOT/arena" && for c in init-prelude cedar mathlib; do ./lka.py build-test "$c"; done)
cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
for arm in control candidate; do
  pgo="$ROOT/pgo-$arm"; rm -rf "$pgo"; mkdir -p "$pgo"
  export CARGO_TARGET_DIR="$ROOT/target-$arm"
  export RUSTFLAGS="-C target-cpu=native -C profile-generate=$pgo"
  (cd "$ROOT/$arm" && cargo build --release --locked -q) > "$OUT/$arm.pgo-build.log" 2>&1
  "$CARGO_TARGET_DIR/release/sokonanoda" "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" > "$OUT/$arm.pgo.stdout" 2> "$OUT/$arm.pgo.stderr"
  nix shell "$LLVM_FLAKE" -c llvm-profdata merge -o "$pgo/merged.profdata" "$pgo"
  export RUSTFLAGS="-C target-cpu=native -C profile-use=$pgo/merged.profdata"
  (cd "$ROOT/$arm" && cargo build --release --locked -q) > "$OUT/$arm.release-build.log" 2>&1
  cp "$CARGO_TARGET_DIR/release/sokonanoda" "$ROOT/$arm-checker"
  echo "V91_${arm^^}_PGO_BUILD=PASS"
done
python3 "$SRC/measure_prune_dm_v88.py" "$ROOT"
python3 - "$OUT" <<'PY'
import json,sys
from pathlib import Path
out=Path(sys.argv[1]); d=json.loads((out/'results.json').read_text()); q=json.loads((out/'qualification.json').read_text())
assert q['no_new_test_failures'] and not q['release_qualified']; assert d['status']=='COMPLETE'
c=d['corpora']; cedar=c['cedar']['delta_percent']; mathlib=c['mathlib']['delta_percent']
decision='REPEAT_AND_ABLATE' if cedar <= -1.0 and mathlib <= -1.0 else 'REJECT'
record={'schema':1,'candidate':'epoch-invalidation-v91','source_evidence':json.loads((out/'source-evidence.json').read_text()),'qualification':q,'benchmark':d,'acceptance_gate':{'cedar_max_delta_percent':-1.0,'mathlib_max_delta_percent':-1.0},'decision':decision,'release_promoted':False}
(out/'experiment.json').write_text(json.dumps(record,indent=2))
print(f'V91_CEDAR_DELTA_PERCENT={cedar:.4f}'); print(f'V91_MATHLIB_DELTA_PERCENT={mathlib:.4f}'); print('V91_DECISION='+decision+'__NO_RELEASE_PROMOTION')
PY
