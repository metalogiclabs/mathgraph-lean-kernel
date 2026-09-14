#!/usr/bin/env bash
set -euo pipefail

: "${MDA_MASK:?MDA_MASK required}"
: "${MDA_TEST_DIR:?MDA_TEST_DIR required}"

GENESIS_BASE=16ccc0ed1c28961e411452d1c1a608761d73929e
FULL=d6a73279e6765e637f9741180cefbd7ef957d8e5
ROOT="/tmp/mda-bidir-v1-mask-${MDA_MASK}"
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

write_result () {
  local direction="$1"
  local class="$2"
  local patch="$3"
  local source_hash="$4"
  local cargo_rc="$5"
  local gate="$6"
  python3 - "$ROOT/evidence/${direction}.json" "$direction" "$MDA_MASK" "$class" "$patch" "$source_hash" "$cargo_rc" "$gate" <<'PY'
import json,sys
p,direction,mask,cls,patch,source_hash,cargo_rc,gate=sys.argv[1:]
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
 "schema":"mda-bidirectional-convergence-v1",
 "direction":direction,
 "mask":m,
 "retained_count":m.bit_count(),
 "retained":[{"bit":i,"commit":c,"name":n} for i,(c,n) in enumerate(commits) if m&(1<<i)],
 "contracted":[{"bit":i,"commit":c,"name":n} for i,(c,n) in enumerate(commits) if not m&(1<<i)],
 "classification":cls,
 "patch_status":patch,
 "source_payload_sha256":None if source_hash=="NA" else source_hash,
 "cargo_test_rc":None if cargo_rc=="NA" else int(cargo_rc),
 "semantic_gate":gate,
 "lawful":cls=="LAWFUL",
}
open(p,"w").write(json.dumps(row,indent=2)+"\n")
PY
}

semantic_gate () {
  local direction="$1"
  local dir="$2"
  local out="$ROOT/out/$direction"
  mkdir -p "$out"

  set +e
  /usr/bin/time -f 'wall=%e user=%U sys=%S rss_kb=%M' -o "$out/cargo-test.time"     cargo test --manifest-path "$dir/Cargo.toml" --release --locked -q     >"$out/cargo-test.out" 2>"$out/cargo-test.err"
  local cargo_rc=$?
  set -e

  if [ "$cargo_rc" -ne 0 ]; then
    local h
    h="$(payload_hash "$dir")"
    write_result "$direction" "UNLAWFUL_SOURCE_REPLAY" "PASS" "$h" "$cargo_rc" "NOT_RUN"
    return
  fi

  cargo build --manifest-path "$dir/Cargo.toml" --release --locked -q
  local bin="$dir/target/release/sokonanoda"
  local gate=PASS

  run_case () {
    local test="$1"
    local want="$2"
    local file="$MDA_TEST_DIR/$test.ndjson"
    set +e
    "$bin" "$ROOT/config.json" < "$file" >"$out/$test.out" 2>"$out/$test.err"
    local rc=$?
    set -e
    printf '%s\twant=%s\trc=%s\n' "$test" "$want" "$rc" >> "$out/arena-fast-gate.tsv"
    if [ "$rc" -ne "$want" ]; then
      gate=FAIL
    fi
  }

  : > "$out/arena-fast-gate.tsv"
  run_case init-prelude 0
  run_case extra-rec 1
  run_case rec-missing-ih 1
  run_case proj-of-stuck-prop 1
  run_case proj-of-subst-prop 1

  local h
  h="$(payload_hash "$dir")"
  if [ "$gate" = PASS ]; then
    write_result "$direction" "LAWFUL" "PASS" "$h" "$cargo_rc" "PASS"
  else
    write_result "$direction" "UNLAWFUL_SEMANTIC_REPLAY" "PASS" "$h" "$cargo_rc" "FAIL"
  fi
}

# GENESIS: add retained atoms from below.
gpatch=PASS
for bit in 0 1 2 3 4 5; do
  if (( MDA_MASK & (1 << bit) )); then
    echo "GENESIS_APPLY bit=$bit commit=${COMMITS[$bit]}" | tee -a "$ROOT/evidence/genesis-patches.txt"
    set +e
    git -C "$ROOT/genesis" cherry-pick --no-commit "${COMMITS[$bit]}"       >"$ROOT/out/genesis-cherry-$bit.out" 2>"$ROOT/out/genesis-cherry-$bit.err"
    rc=$?
    set -e
    if [ "$rc" -ne 0 ]; then
      gpatch=UNREACHABLE_PATCH
      git -C "$ROOT/genesis" cherry-pick --abort >/dev/null 2>&1 || true
      break
    fi
  fi
done
if [ "$gpatch" = PASS ]; then
  semantic_gate genesis "$ROOT/genesis"
else
  write_result genesis "UNREACHABLE_PATCH" "$gpatch" NA NA NOT_RUN
fi

# SOLVENT: remove unretained atoms from above.
spatch=PASS
for bit in 5 4 3 2 1 0; do
  if (( (MDA_MASK & (1 << bit)) == 0 )); then
    echo "SOLVENT_REVERT bit=$bit commit=${COMMITS[$bit]}" | tee -a "$ROOT/evidence/solvent-patches.txt"
    set +e
    git -C "$ROOT/solvent" revert --no-commit "${COMMITS[$bit]}"       >"$ROOT/out/solvent-revert-$bit.out" 2>"$ROOT/out/solvent-revert-$bit.err"
    rc=$?
    set -e
    if [ "$rc" -ne 0 ]; then
      spatch=UNREACHABLE_PATCH
      git -C "$ROOT/solvent" revert --abort >/dev/null 2>&1 || true
      break
    fi
  fi
done
if [ "$spatch" = PASS ]; then
  semantic_gate solvent "$ROOT/solvent"
else
  write_result solvent "UNREACHABLE_PATCH" "$spatch" NA NA NOT_RUN
fi

python3 - "$ROOT/evidence" <<'PY'
import json,pathlib,sys
root=pathlib.Path(sys.argv[1])
g=json.loads((root/"genesis.json").read_text())
s=json.loads((root/"solvent.json").read_text())
pair={
 "mask":g["mask"],
 "retained_count":g["retained_count"],
 "genesis":g,
 "solvent":s,
 "both_lawful":g["lawful"] and s["lawful"],
 "same_source_payload":(
   g["lawful"] and s["lawful"] and
   g["source_payload_sha256"]==s["source_payload_sha256"]
 ),
}
(root/"pair.json").write_text(json.dumps(pair,indent=2)+"\n")
print(
 "MDA_BIDIR_MASK",
 pair["mask"],
 "G="+g["classification"],
 "S="+s["classification"],
 "same_source="+str(pair["same_source_payload"])
)
PY
