#!/usr/bin/env bash
set -euo pipefail

: "${REV:?REV required}"
: "${LABEL:?LABEL required}"

ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT="/tmp/mda-lineage-${LABEL}"
rm -rf "$ROOT"
mkdir -p "$ROOT/evidence" "$ROOT/out"

echo "MDA_LINEAGE_LABEL=$LABEL"
echo "MDA_LINEAGE_REV=$REV"
echo "MDA_LINEAGE_ARENA=$ARENA"

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
nix develop -c ./lka.py build-test mathlib >/dev/null

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/repo"
git -C "$ROOT/repo" checkout -q "$REV"

cd "$ROOT/repo"

set +e
cargo test --release --locked -q >"$ROOT/out/cargo-test.out" 2>"$ROOT/out/cargo-test.err"
test_rc=$?
set -e

if [ "$test_rc" -ne 0 ]; then
  if grep -qE 'reject_unlisted_recursor|reject_rec_rule_with_forged_lambda_domains' "$ROOT/out/cargo-test.out" "$ROOT/out/cargo-test.err"; then
    class="UNLAWFUL_PROTECTED_REPLAY"
  elif grep -qE 'could not compile|error\[E[0-9]+' "$ROOT/out/cargo-test.out" "$ROOT/out/cargo-test.err"; then
    class="INVALID_TRANSITION_SNAPSHOT"
  else
    class="UNKNOWN_TEST_FAILURE"
  fi
  echo "MDA_LINEAGE_CLASSIFICATION label=$LABEL class=$class test_rc=$test_rc"
  python3 - "$ROOT" "$LABEL" "$REV" "$class" "$test_rc" <<'PY'
import json,pathlib,sys
root=pathlib.Path(sys.argv[1])
data={
  "label":sys.argv[2],
  "rev":sys.argv[3],
  "classification":sys.argv[4],
  "test_rc":int(sys.argv[5]),
  "measured":False,
  "claim_boundary":"Non-lawful or non-buildable snapshots are classified, not performance-compared."
}
(root/"evidence/result.json").write_text(json.dumps(data,indent=2)+"\n")
PY
  echo "MDA_LINEAGE_COMPLETE=CLASSIFIED"
  exit 0
fi

echo "MDA_LINEAGE_TESTS=PASS"
class="LAWFUL"

rm -rf pgo
RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$ROOT/repo/pgo" cargo build --release --locked -q
target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null 2>/dev/null
cd "$ROOT/arena"
nix develop -c llvm-profdata merge -o "$ROOT/repo/pgo/merged.profdata" "$ROOT/repo/pgo"
cd "$ROOT/repo"
RUSTFLAGS="-C target-cpu=native -Cprofile-use=$ROOT/repo/pgo/merged.profdata" cargo build --release --locked -q
echo "MDA_LINEAGE_PGO=PASS"

set +e
/usr/bin/time -f 'wall=%e user=%U sys=%S rss_kb=%M' -o "$ROOT/out/mathlib.time"   "$ROOT/repo/target/release/sokonanoda" "$ROOT/config.json"   < "$ROOT/arena/_build/tests/mathlib.ndjson" >/dev/null 2>"$ROOT/out/mathlib.err"
rc=$?
set -e

echo "MDA_LINEAGE_RESULT label=$LABEL rev=$REV rc=$rc $(cat "$ROOT/out/mathlib.time")"

python3 - "$ROOT" "$LABEL" "$REV" "$rc" <<'PY'
import json,pathlib,re,sys
root=pathlib.Path(sys.argv[1]); label=sys.argv[2]; rev=sys.argv[3]; rc=int(sys.argv[4])
s=(root/"out/mathlib.time").read_text().strip()
row={"label":label,"rev":rev,"classification":"LAWFUL","rc":rc,"measured":True}
for k,v in re.findall(r'(wall|user|sys|rss_kb)=([0-9.]+)',s):
    row[k]=int(v) if k=="rss_kb" else float(v)
row["claim_boundary"]="screening measurement only; no retired-instruction authority on this runner"
(root/"evidence/result.json").write_text(json.dumps(row,indent=2)+"\n")
PY

[ "$rc" -eq 0 ]
echo "MDA_LINEAGE_COMPLETE=PASS"
