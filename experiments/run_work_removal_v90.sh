#!/usr/bin/env bash
set -euo pipefail
MODE=${1:?preflight or benchmark required}
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
RAW=7b51784fe4ec9b82bf7a20c71ba6bf803a4ed7c0
UPSTREAM=ceaabb593e830dd318bfefd1675be3142fad8eb7
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
LLVM_FLAKE='github:NixOS/nixpkgs/0ad6f47ea4fe188f4bc8f0380f93ae8523337c6c#llvmPackages_21.llvm'
ROOT=/tmp/v90
OUT=$ROOT/out
SRC=$GITHUB_WORKSPACE/experiments
mkdir -p "$OUT"
export RUSTFLAGS='-C target-cpu=native'

prepare() {
  rm -rf "$ROOT/control" "$ROOT/candidate" "$ROOT/ablated"
  mkdir -p "$ROOT/control" "$ROOT/candidate" "$ROOT/ablated"
  git -C "$GITHUB_WORKSPACE" fetch -q origin "$BASE" "$RAW"
  git -C "$GITHUB_WORKSPACE" fetch -q https://github.com/intgrah/sokonanoda.git "$UPSTREAM"
  test "$(git -C "$GITHUB_WORKSPACE" rev-parse "$UPSTREAM^")" = "$RAW"
  git -C "$GITHUB_WORKSPACE" archive "$BASE" | tar -x -C "$ROOT/control"
  git -C "$GITHUB_WORKSPACE" archive "$UPSTREAM" | tar -x -C "$ROOT/candidate"
  git -C "$GITHUB_WORKSPACE" archive "$RAW" | tar -x -C "$ROOT/ablated"
  python3 "$SRC/install_work_removal_v90.py" "$ROOT/candidate" upstream
  python3 "$SRC/install_work_removal_v90.py" "$ROOT/ablated" raw
  diff -qr "$ROOT/control" "$ROOT/ablated" > "$OUT/ablation.diff"
  echo 'V90_EXACT_SOURCE_ABLATION=PASS'
  git -C "$GITHUB_WORKSPACE" diff "$RAW" "$UPSTREAM" -- src > "$OUT/upstream.patch"
  python3 - "$ROOT" <<'PY'
from pathlib import Path
import hashlib,json,sys
r=Path(sys.argv[1])
def manifest(p):
    return {str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(p.rglob('*')) if f.is_file()}
a=manifest(r/'control');b=manifest(r/'candidate');c=manifest(r/'ablated')
assert a==c and a!=b
assert set(a)==set(b), 'source file set changed'
(r/'out'/'source-manifest.json').write_text(json.dumps({'control':a,'candidate':b,'ablated':c},indent=2)+'\n')
print('V90_SOURCE_MANIFEST=PASS')
PY
}

prepare
if [[ "$MODE" == preflight ]]; then
  for arm in control candidate; do
    export CARGO_TARGET_DIR="$ROOT/target-$arm"
    set +e
    (cd "$ROOT/$arm" && cargo test --locked) > "$OUT/$arm.tests.log" 2>&1
    rc=$?
    set -e
    printf '%s\n' "$rc" > "$OUT/$arm.tests.rc"
  done
  python3 - "$OUT" <<'PY'
from pathlib import Path
import json,re,sys
out=Path(sys.argv[1]);known={'tests::util::reject_rec_rule_with_forged_lambda_domains','tests::util::reject_unlisted_recursor'}
pat=re.compile(r'^test (\S+)(?: - should panic)? \.\.\. (ok|FAILED)$',re.M)
def read(arm):
    text=(out/(arm+'.tests.log')).read_text()
    rows=pat.findall(text); assert len(rows)>=40, (arm,len(rows))
    names=[n for n,_ in rows]; assert len(names)==len(set(names))
    return {'rc':int((out/(arm+'.tests.rc')).read_text()),'count':len(rows),
            'passed':sum(s=='ok' for _,s in rows),'failures':sorted(n for n,s in rows if s=='FAILED'),
            'names':names}
a,b=read('control'),read('candidate')
assert set(a['names'])==set(b['names']), 'test inventory changed'
assert not (set(b['failures'])-set(a['failures'])), 'new test failures'
assert set(a['failures'])<=known, 'unexpected control failures'
assert set(b['failures'])<=known, 'unexpected candidate failures'
assert (a['rc']==0)==(not a['failures']) and (b['rc']==0)==(not b['failures'])
qualified=a['rc']==b['rc']==0 and not a['failures'] and not b['failures']
q={'control':a,'candidate':b,'no_new_test_failures':True,'release_qualified':qualified,
   'known_fixture_blockers':sorted(set(a['failures'])|set(b['failures']))}
(out/'qualification.json').write_text(json.dumps(q,indent=2)+'\n')
print('V90_NO_NEW_TEST_FAILURES=PASS')
print('V90_RELEASE_QUALIFICATION='+('PASS' if qualified else 'BLOCKED_KNOWN_FIXTURES'))
PY
  exit 0
fi
if [[ "$MODE" != benchmark ]]; then echo 'Unknown mode' >&2; exit 2; fi
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
  rm -rf "$pgo"
  mkdir -p "$pgo"
  export CARGO_TARGET_DIR="$ROOT/target-$arm-pgo"
  export RUSTFLAGS="-C target-cpu=native -C profile-generate=$pgo"
  (cd "$ROOT/$arm" && cargo build --release --locked -q) > "$OUT/$arm.pgo-build.log" 2>&1
  "$CARGO_TARGET_DIR/release/sokonanoda" "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" > "$OUT/$arm.pgo.stdout" 2> "$OUT/$arm.pgo.stderr"
  nix shell "$LLVM_FLAKE" -c llvm-profdata merge -o "$pgo/merged.profdata" "$pgo"
  test -s "$pgo/merged.profdata"
  export CARGO_TARGET_DIR="$ROOT/target-$arm-release"
  export RUSTFLAGS="-C target-cpu=native -C profile-use=$pgo/merged.profdata"
  (cd "$ROOT/$arm" && cargo build --release --locked -q) > "$OUT/$arm.release-build.log" 2>&1
  cp "$CARGO_TARGET_DIR/release/sokonanoda" "$ROOT/$arm-checker"
  echo "V90_${arm^^}_PGO_BUILD=PASS"
done
python3 "$SRC/measure_work_removal_v90.py" "$ROOT"
