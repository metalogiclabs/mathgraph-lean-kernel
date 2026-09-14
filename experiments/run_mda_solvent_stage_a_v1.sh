#!/usr/bin/env bash
set -euo pipefail

: "${MDA_MASK:?set MDA_MASK}"

BASE=d6a73279e6765e637f9741180cefbd7ef957d8e5
ROOT="/tmp/mda-solvent-v1-mask-${MDA_MASK}"
rm -rf "$ROOT"
mkdir -p "$ROOT/evidence" "$ROOT/out"

# Revert selected retained capability atoms newest -> oldest.
COMMITS=(
  801cb6d918d0
  2de1895a52d2
  91ba5db40292
  eaf479a135c0
  5daa4f66c1fa
  d6a73279e676
)
NAMES=(
  equal_hint_short_asymmetric_spines
  reject_underived_orphan_recursors
  wide_framed_exact_deep_reads
  wide_read_projected_env_cache
  exact_env_keys_past_64
  bottom_up_wide_one_pass_projection
)

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/candidate"
cd "$ROOT/candidate"
git checkout -q "$BASE"

{
  echo "schema=mda-solvent-v1-stage-a"
  echo "base=$BASE"
  echo "mask=$MDA_MASK"
} > "$ROOT/evidence/meta.txt"

python3 - "$MDA_MASK" "$ROOT/evidence/configuration.json" <<'PY'
import json,sys
m=int(sys.argv[1])
commits=[
("801cb6d918d0","equal_hint_short_asymmetric_spines"),
("2de1895a52d2","reject_underived_orphan_recursors"),
("91ba5db40292","wide_framed_exact_deep_reads"),
("eaf479a135c0","wide_read_projected_env_cache"),
("5daa4f66c1fa","exact_env_keys_past_64"),
("d6a73279e676","bottom_up_wide_one_pass_projection"),
]
json.dump({
 "mask":m,
 "contracted":[{"bit":i,"commit":c,"name":n} for i,(c,n) in enumerate(commits) if m&(1<<i)],
 "retained":[{"bit":i,"commit":c,"name":n} for i,(c,n) in enumerate(commits) if not m&(1<<i)],
},open(sys.argv[2],"w"),indent=2)
PY

patch_status=PASS
for bit in 5 4 3 2 1 0; do
  if (( MDA_MASK & (1 << bit) )); then
    commit="${COMMITS[$bit]}"
    name="${NAMES[$bit]}"
    echo "MDA_SOLVENT_REVERT bit=$bit name=$name commit=$commit" | tee -a "$ROOT/evidence/reverts.txt"
    set +e
    git revert --no-commit "$commit" >"$ROOT/out/revert-${bit}.out" 2>"$ROOT/out/revert-${bit}.err"
    rc=$?
    set -e
    if [ "$rc" -ne 0 ]; then
      patch_status=UNREACHABLE_PATCH
      git revert --abort >/dev/null 2>&1 || true
      break
    fi
  fi
done

echo "patch_status=$patch_status" | tee "$ROOT/evidence/status.txt"
if [ "$patch_status" != PASS ]; then
  echo "MDA_SOLVENT_STAGE_A=$patch_status"
  exit 0
fi

git diff --binary "$BASE" > "$ROOT/evidence/candidate.patch"
git diff --stat "$BASE" > "$ROOT/evidence/candidate.stat"
git diff --check

set +e
/usr/bin/time -f 'wall=%e user=%U sys=%S rss_kb=%M' -o "$ROOT/evidence/cargo-test.time"   cargo test --release --locked -q >"$ROOT/out/cargo-test.out" 2>"$ROOT/out/cargo-test.err"
test_rc=$?
set -e

if [ "$test_rc" -ne 0 ]; then
  echo "build_test_status=UNLAWFUL_SOURCE_REPLAY" >> "$ROOT/evidence/status.txt"
  echo "cargo_test_rc=$test_rc" >> "$ROOT/evidence/status.txt"
  echo "MDA_SOLVENT_STAGE_A=UNLAWFUL_SOURCE_REPLAY"
  exit 0
fi

cargo build --release --locked -q
echo "build_test_status=PASS" >> "$ROOT/evidence/status.txt"
echo "MDA_SOLVENT_STAGE_A_SOURCE=PASS"

: "${MDA_TEST_DIR:?set MDA_TEST_DIR to prepared pinned Arena fast-gate exports}"

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

: > "$ROOT/evidence/arena-fast-gate.tsv"
run_case () {
  local test="$1"
  local want="$2"
  local file="$MDA_TEST_DIR/$test.ndjson"
  if [ ! -s "$file" ]; then
    echo "missing_test=$test" >> "$ROOT/evidence/status.txt"
    echo "MDA_SOLVENT_STAGE_A=HARNESS_MISSING_TEST"
    exit 2
  fi
  set +e
  target/release/sokonanoda "$ROOT/config.json" < "$file" >"$ROOT/out/$test.out" 2>"$ROOT/out/$test.err"
  rc=$?
  set -e
  printf '%s\twant=%s\trc=%s\n' "$test" "$want" "$rc" | tee -a "$ROOT/evidence/arena-fast-gate.tsv"
  if [ "$rc" -ne "$want" ]; then
    echo "arena_fast_gate_status=UNLAWFUL_SEMANTIC_REPLAY" >> "$ROOT/evidence/status.txt"
    echo "failed_test=$test" >> "$ROOT/evidence/status.txt"
    echo "MDA_SOLVENT_STAGE_A=UNLAWFUL_SEMANTIC_REPLAY"
    exit 0
  fi
}

run_case init-prelude 0
run_case extra-rec 1
run_case rec-missing-ih 1
run_case proj-of-stuck-prop 1
run_case proj-of-subst-prop 1

echo "arena_fast_gate_status=PASS" >> "$ROOT/evidence/status.txt"
git diff --numstat "$BASE" > "$ROOT/evidence/candidate.numstat"
echo "MDA_SOLVENT_STAGE_A=PASS"
