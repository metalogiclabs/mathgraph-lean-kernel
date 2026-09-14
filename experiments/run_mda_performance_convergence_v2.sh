#!/usr/bin/env bash
set -euo pipefail

: "${MDA_MASK:?MDA_MASK required}"
: "${MDA_TEST_DIR:?MDA_TEST_DIR required}"

GENESIS_BASE=16ccc0ed1c28961e411452d1c1a608761d73929e
FULL=d6a73279e6765e637f9741180cefbd7ef957d8e5
ROOT="/tmp/mda-perf-v2-mask-${MDA_MASK}"
rm -rf "$ROOT"
mkdir -p "$ROOT/evidence" "$ROOT/out"

COMMITS=(
  801cb6d918d0e383e4c6a3c6017ef945d42a0698
  2de1895a52d21ad266b77002defe3e6bc69bbcfd
  91ba5db4029290b257a08494559ec3283cddbee3
  eaf479a135c02e0daad6760eff9e049dd9f63576
  5daa4f66c1fa63b44d2dd02e96bd7303e6ec0f71
  d6a73279e6765e637f9741180cefbd7ef957d8e5
)
NAMES=(
  equal_hint_short_asymmetric_spines
  reject_underived_orphan_recursors
  wide_framed_exact_deep_reads
  wide_read_projected_env_cache
  exact_env_keys_past_64
  bottom_up_wide_one_pass_projection
)

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/repo"
git -C "$ROOT/repo" worktree add -q --detach "$ROOT/genesis" "$GENESIS_BASE"
git -C "$ROOT/repo" worktree add -q --detach "$ROOT/solvent" "$FULL"

payload_hash () {
  local dir="$1"
  (
    cd "$dir"
    {
      printf 'Cargo.toml  '; sha256sum Cargo.toml | awk '{print $1}'
      printf 'Cargo.lock  '; sha256sum Cargo.lock | awk '{print $1}'
      find src tests -type f -print0 | sort -z | while IFS= read -r -d '' f; do
        printf '%s  ' "$f"
        sha256sum "$f" | awk '{print $1}'
      done
    } | sha256sum | awk '{print $1}'
  )
}

write_base_result () {
  local direction="$1"
  local classification="$2"
  local source_hash="$3"
  python3 - "$ROOT/evidence/${direction}.json" "$direction" "$MDA_MASK" "$classification" "$source_hash" <<'PY'
import json,sys
p,direction,mask,classification,source_hash=sys.argv[1:]
m=int(mask)
commits=[
("801cb6d918d0e383e4c6a3c6017ef945d42a0698","equal_hint_short_asymmetric_spines"),
("2de1895a52d21ad266b77002defe3e6bc69bbcfd","reject_underived_orphan_recursors"),
("91ba5db4029290b257a08494559ec3283cddbee3","wide_framed_exact_deep_reads"),
("eaf479a135c02e0daad6760eff9e049dd9f63576","wide_read_projected_env_cache"),
("5daa4f66c1fa63b44d2dd02e96bd7303e6ec0f71","exact_env_keys_past_64"),
("d6a73279e6765e637f9741180cefbd7ef957d8e5","bottom_up_wide_one_pass_projection"),
]
row={
 "schema":"mda-performance-convergence-v2",
 "direction":direction,
 "mask":m,
 "retained_count":m.bit_count(),
 "retained":[{"bit":i,"commit":c,"name":n} for i,(c,n) in enumerate(commits) if m&(1<<i)],
 "classification":classification,
 "lawful":classification=="LAWFUL",
 "source_payload_sha256":source_hash if source_hash!="NA" else None,
 "performance":{},
}
open(p,"w").write(json.dumps(row,indent=2)+"\n")
PY
}

append_perf () {
  local direction="$1"
  local test="$2"
  local rc="$3"
  local ir="$4"
  python3 - "$ROOT/evidence/${direction}.json" "$test" "$rc" "$ir" <<'PY'
import json,sys
p,test,rc,ir=sys.argv[1:]
d=json.load(open(p))
d["performance"][test]={"rc":int(rc),"callgrind_instructions":int(ir)}
open(p,"w").write(json.dumps(d,indent=2)+"\n")
PY
}

construct_genesis () {
  for bit in 0 1 2 3 4 5; do
    if (( MDA_MASK & (1 << bit) )); then
      echo "GENESIS_APPLY bit=$bit commit=${COMMITS[$bit]}" | tee -a "$ROOT/evidence/genesis-patches.txt"
      if ! git -C "$ROOT/genesis" cherry-pick --no-commit "${COMMITS[$bit]}"           >"$ROOT/out/genesis-cherry-$bit.out" 2>"$ROOT/out/genesis-cherry-$bit.err"; then
        git -C "$ROOT/genesis" cherry-pick --abort >/dev/null 2>&1 || true
        return 1
      fi
    fi
  done
}

construct_solvent () {
  for bit in 5 4 3 2 1 0; do
    if (( (MDA_MASK & (1 << bit)) == 0 )); then
      echo "SOLVENT_REVERT bit=$bit commit=${COMMITS[$bit]}" | tee -a "$ROOT/evidence/solvent-patches.txt"
      if ! git -C "$ROOT/solvent" revert --no-commit "${COMMITS[$bit]}"           >"$ROOT/out/solvent-revert-$bit.out" 2>"$ROOT/out/solvent-revert-$bit.err"; then
        git -C "$ROOT/solvent" revert --abort >/dev/null 2>&1 || true
        return 1
      fi
    fi
  done
}

semantic_and_build () {
  local direction="$1"
  local dir="$2"
  local out="$ROOT/out/$direction"
  mkdir -p "$out"

  set +e
  cargo test --manifest-path "$dir/Cargo.toml" --release --locked -q     >"$out/cargo-test.out" 2>"$out/cargo-test.err"
  local cargo_rc=$?
  set -e
  local h
  h="$(payload_hash "$dir")"
  if [ "$cargo_rc" -ne 0 ]; then
    write_base_result "$direction" "UNLAWFUL_SOURCE_REPLAY" "$h"
    return 1
  fi

  cargo build --manifest-path "$dir/Cargo.toml" --release --locked -q
  local bin="$dir/target/release/sokonanoda"

  local gate=PASS
  run_case () {
    local test="$1"
    local want="$2"
    local file="$MDA_TEST_DIR/$test.ndjson"
    set +e
    "$bin" "$ROOT/config.json" < "$file" >"$out/${test//\//_}.out" 2>"$out/${test//\//_}.err"
    local rc=$?
    set -e
    printf '%s\twant=%s\trc=%s\n' "$test" "$want" "$rc" >> "$out/semantic.tsv"
    if [ "$rc" -ne "$want" ]; then gate=FAIL; fi
  }

  : > "$out/semantic.tsv"
  run_case init-prelude 0
  run_case extra-rec 1
  run_case rec-missing-ih 1
  run_case proj-of-stuck-prop 1
  run_case proj-of-subst-prop 1

  if [ "$gate" != PASS ]; then
    write_base_result "$direction" "UNLAWFUL_SEMANTIC_REPLAY" "$h"
    return 1
  fi

  write_base_result "$direction" "LAWFUL" "$h"
  return 0
}

measure_perf () {
  local direction="$1"
  local dir="$2"
  local out="$ROOT/out/$direction"
  local bin="$dir/target/release/sokonanoda"
  for test in perf/grind-ring-5 perf/app-lam perf/beta-ladder perf/let-ladder; do
    local safe="${test//\//_}"
    local cg="$out/$safe.callgrind"
    local vg="$out/$safe.valgrind.err"
    set +e
    valgrind --tool=callgrind --callgrind-out-file="$cg"       "$bin" "$ROOT/config.json" < "$MDA_TEST_DIR/$test.ndjson"       >"$out/$safe.perf.out" 2>"$vg"
    local rc=$?
    set -e
    local ir
    ir="$(awk '/^summary:/ {print $2; exit}' "$cg")"
    if [ -z "$ir" ]; then
      echo "missing callgrind summary direction=$direction test=$test" >&2
      exit 3
    fi
    append_perf "$direction" "$test" "$rc" "$ir"
    printf '%s\trc=%s\tinstructions=%s\n' "$test" "$rc" "$ir" | tee -a "$out/performance.tsv"
  done
}

if ! construct_genesis; then
  write_base_result genesis "UNREACHABLE_PATCH" NA
else
  semantic_and_build genesis "$ROOT/genesis" || true
fi

if ! construct_solvent; then
  write_base_result solvent "UNREACHABLE_PATCH" NA
else
  semantic_and_build solvent "$ROOT/solvent" || true
fi

python3 - "$ROOT/evidence" <<'PY'
import json,pathlib,sys
root=pathlib.Path(sys.argv[1])
g=json.load(open(root/"genesis.json")); s=json.load(open(root/"solvent.json"))
if not (g["lawful"] and s["lawful"]):
    raise SystemExit(f"Frozen admissible mask unexpectedly non-lawful: G={g['classification']} S={s['classification']}")
if g["source_payload_sha256"] != s["source_payload_sha256"]:
    raise SystemExit("Source payload mismatch between directions")
PY

measure_perf genesis "$ROOT/genesis"
measure_perf solvent "$ROOT/solvent"

python3 - "$ROOT/evidence" <<'PY'
import json,pathlib,sys
root=pathlib.Path(sys.argv[1])
g=json.load(open(root/"genesis.json")); s=json.load(open(root/"solvent.json"))
pair={
 "schema":"mda-performance-convergence-v2-pair",
 "mask":g["mask"],
 "retained_count":g["retained_count"],
 "same_source_payload":g["source_payload_sha256"]==s["source_payload_sha256"],
 "genesis":g,
 "solvent":s,
}
(root/"pair.json").write_text(json.dumps(pair,indent=2)+"\n")
print("MDA_PERF_V2_MASK",pair["mask"],"same_source="+str(pair["same_source_payload"]))
for d in ("genesis","solvent"):
    print("MDA_PERF_V2_DIRECTION",d,json.dumps(pair[d]["performance"],sort_keys=True))
PY
