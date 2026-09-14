#!/usr/bin/env bash
set -euo pipefail

BASE=c6d445a954def8922490d0cd874ea134b45463dd
FREEZE=e5db03ccba629f5dc8b3e2126bc55f000a76065b
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/mda-auto-train-v2
POLICY_DIR="$ROOT/policies"
EVIDENCE="$ROOT/evidence"
BIN="$ROOT/bin"
TRAIN=(con-leche perf/app-lam perf/beta-ladder perf/let-ladder)

rm -rf "$ROOT"
mkdir -p "$POLICY_DIR" "$EVIDENCE" "$BIN" "$ROOT/census"

git diff --exit-code "$FREEZE" -- mda/AUTONOMOUS_CHECKER_GENESIS_V2.md
git diff --quiet "$BASE" -- src/eval.rs src/main.rs
echo "MDA_V2_TRAIN_FREEZE=PASS"

cp src/eval.rs "$ROOT/clean-eval.rs"
cp src/main.rs "$ROOT/clean-main.rs"

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cd "$ROOT/arena"
for t in "${TRAIN[@]}"; do
  echo "MDA_V2_BUILD_TRAIN=$t"
  nix develop -c ./lka.py build-test "$t" >/dev/null
done
cd "$GITHUB_WORKSPACE"

# Census with the expanded observation language.
python3 scripts/mda_autonomous_cache_genesis_v2.py instrument src/eval.rs src/main.rs
cargo test --release --locked -q
RUSTFLAGS="-C target-cpu=native" cargo build --release --locked -q
cp target/release/sokonanoda "$BIN/instrumented"

for t in "${TRAIN[@]}"; do
  safe="$(printf '%s' "$t" | tr '/' '_')"
  MDA_V2_CACHE_CENSUS=1 "$BIN/instrumented" "$ROOT/config.json"     < "$ROOT/arena/_build/tests/$t.ndjson"     > "$ROOT/census/$safe.stdout" 2> "$ROOT/census/$safe.stderr"
  echo "MDA_V2_CENSUS_PASS=$t"
done

python3 scripts/mda_autonomous_cache_genesis_v2.py parse-census   "$EVIDENCE/training-census.json" "$ROOT"/census/*.stderr
python3 scripts/mda_autonomous_cache_genesis_v2.py make-policies   "$EVIDENCE/training-census.json" "$POLICY_DIR"

cp "$ROOT/clean-eval.rs" src/eval.rs
cp "$ROOT/clean-main.rs" src/main.rs
: > "$EVIDENCE/training-timings.tsv"
: > "$EVIDENCE/training-failures.tsv"

build_current () {
  cargo test --release --locked -q >/dev/null
  RUSTFLAGS="-C target-cpu=native" cargo build --release --locked -q
}

run_label () {
  local label="$1"; local binary="$2"
  for t in "${TRAIN[@]}"; do
    set +e
    "$binary" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" >/dev/null 2>/dev/null
    rc=$?
    set -e
    if [ "$rc" -ne 0 ]; then
      printf '%s\t%s\trc=%s\n' "$label" "$t" "$rc" >> "$EVIDENCE/training-failures.tsv"
      return 1
    fi
    for rep in 1 2; do
      /usr/bin/time -f '%e' -o "$ROOT/t.time"         "$binary" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" >/dev/null 2>/dev/null
      printf '%s\t%s\t%s\t%s\n' "$label" "$t" "$rep" "$(cat "$ROOT/t.time")"         | tee -a "$EVIDENCE/training-timings.tsv"
    done
  done
}

build_current
cp target/release/sokonanoda "$BIN/base"
run_label BASE "$BIN/base"

while IFS= read -r label; do
  [ -n "$label" ] || continue
  echo "MDA_V2_POLICY_BEGIN=$label"
  cp "$ROOT/clean-main.rs" src/main.rs
  python3 scripts/mda_autonomous_cache_genesis_v2.py apply-policy     "$ROOT/clean-eval.rs" "$POLICY_DIR/$label.json" src/eval.rs

  set +e
  build_current
  brc=$?
  set -e
  if [ "$brc" -ne 0 ]; then
    printf '%s\tBUILD\trc=%s\n' "$label" "$brc" >> "$EVIDENCE/training-failures.tsv"
    continue
  fi

  cp target/release/sokonanoda "$BIN/$label"
  set +e
  run_label "$label" "$BIN/$label"
  trc=$?
  set -e
  echo "MDA_V2_POLICY_END=$label rc=$trc"
done < "$POLICY_DIR/labels.txt"

set +e
python3 scripts/mda_autonomous_cache_genesis_v2.py select   "$EVIDENCE/training-timings.tsv" "$POLICY_DIR" "$EVIDENCE/selection.json"
selrc=$?
set -e

if [ "$selrc" -ne 0 ]; then
  echo "MDA_V2_TRAIN_VERDICT=UNKNOWN_NO_TRAINING_WIN_V2"
  exit 0
fi

SELECTED="$(python3 - "$EVIDENCE/selection.json" <<'PY'
import json,sys
print(json.load(open(sys.argv[1]))["selected"]["label"])
PY
)"
cp "$POLICY_DIR/$SELECTED.json" "$EVIDENCE/selected-policy.json"
echo "MDA_V2_TRAIN_SELECTED=$SELECTED"
python3 - "$EVIDENCE/selected-policy.json" <<'PY'
import json,sys
print("MDA_V2_SELECTED_POLICY_JSON="+json.dumps(json.load(open(sys.argv[1])),separators=(",",":"),sort_keys=True))
PY
python3 - "$EVIDENCE/selection.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
print("MDA_V2_SELECTED_METRICS="+json.dumps(d["selected"],separators=(",",":"),sort_keys=True))
PY
echo "MDA_V2_TRAIN_VERDICT=SELECTED_FOR_SEMANTIC_GATE"
