#!/usr/bin/env bash
set -euo pipefail
MODE=${1:?preflight or benchmark required}
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
ROOT=/tmp/v88
OUT=$ROOT/out
SRC=$GITHUB_WORKSPACE/experiments
mkdir -p "$OUT"
export RUSTFLAGS='-C target-cpu=native'

prepare() {
  mkdir -p "$ROOT/control" "$ROOT/candidate"
  git -C "$GITHUB_WORKSPACE" fetch -q origin "$BASE"
  git -C "$GITHUB_WORKSPACE" archive "$BASE" | tar -x -C "$ROOT/control"
  cp -a "$ROOT/control/." "$ROOT/candidate/"
  cp "$SRC/prune_dm_v88.rs" "$ROOT/candidate/src/tests/prune_dm_v88.rs"
  python3 "$SRC/patch_prune_dm_v88.py" "$ROOT/candidate"
  diff -u "$ROOT/control/src/util.rs" "$ROOT/candidate/src/util.rs" > "$OUT/production.patch" || test "$?" -eq 1
  python3 - "$ROOT" <<'PY'
from pathlib import Path
import hashlib,sys
r=Path(sys.argv[1]); a=(r/'control/src/util.rs').read_bytes(); b=(r/'candidate/src/util.rs').read_bytes()
assert hashlib.sha1(b'blob '+str(len(a)).encode()+b'\0'+a).hexdigest()=='a0fab9f758a6fe947585d866d98665d9512c1a2c'
assert a!=b
print('V88_EXACT_SOURCE_DIFF=PASS')
PY
}

if [[ "$MODE" == preflight ]]; then
  prepare
  (cd "$ROOT/control" && PYTHONPATH="$SRC" python3 -m unittest -v test_patch_prune_dm_v88) > "$OUT/patcher-tests.log" 2>&1
  echo 'V88_PATCHER_TESTS=PASS'
  for arm in control candidate; do
    export CARGO_TARGET_DIR="$ROOT/target-$arm"
    (cd "$ROOT/$arm" && cargo test --locked -- prune_dm_v88 --nocapture) > "$OUT/$arm.focused.log" 2>&1
    if [[ "$arm" == candidate ]]; then
      grep -Eq 'test result: ok\. 3 passed; 0 failed;' "$OUT/$arm.focused.log"
    fi
    set +e
    (cd "$ROOT/$arm" && cargo test --locked -- --nocapture) > "$OUT/$arm.tests.log" 2>&1
    rc=$?
    set -e
    printf '%s\n' "$rc" > "$OUT/$arm.tests.rc"
  done
  python3 - "$OUT" <<'PY'
from pathlib import Path
import json,re,sys
r=Path(sys.argv[1]); expected={'tests::util::reject_rec_rule_with_forged_lambda_domains','tests::util::reject_unlisted_recursor'}
result={'control':{},'candidate':{},'release_qualified':False}
for arm,n in [('control',42),('candidate',45)]:
    text=(r/f'{arm}.tests.log').read_text()
    rows=dict(re.findall(r'^test (\S+?)(?: - should panic)? \.\.\. (ok|FAILED)$',text,re.M))
    failures={k for k,v in rows.items() if v=='FAILED'}
    result[arm]={'count':len(rows),'failures':sorted(failures),'rc':int((r/f'{arm}.tests.rc').read_text())}
    assert len(rows)==n,(arm,len(rows),n)
    assert failures==expected,(arm,failures)
    assert result[arm]['rc']==101,(arm,result[arm]['rc'])
    assert re.search(r'test result: FAILED\.',text),arm
assert all(k in result['candidate']['failures'] for k in result['control']['failures'])
result['no_new_test_failures']=True
(r/'qualification.json').write_text(json.dumps(result,indent=2))
print('V88_NO_NEW_TEST_FAILURES=PASS')
print('V88_RELEASE_QUALIFICATION=BLOCKED_KNOWN_FIXTURES')
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
  echo "V88_${arm^^}_PGO_BUILD=PASS"
done
python3 "$SRC/measure_prune_dm_v88.py" "$ROOT"
