#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
ROOT=/tmp/v83
rm -rf "$ROOT"
mkdir -p "$ROOT/out"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
echo "V83_BASE=$BASE"
echo "V83_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)"
cd "$ROOT/arena"
for corpus in std cedar mathlib; do nix develop -c ./lka.py build-test "$corpus" >/dev/null; done
cd "$ROOT/base"
RUSTFLAGS='-C target-cpu=native' CARGO_TARGET_DIR="$ROOT/target-clean" cargo build --release --locked -q
cp "$ROOT/target-clean/release/sokonanoda" "$ROOT/clean.bin"
RUSTFLAGS='-C target-cpu=native -C debuginfo=1 -C force-frame-pointers=yes' CARGO_TARGET_DIR="$ROOT/target-profile" cargo build --release --locked -q
cp "$ROOT/target-profile/release/sokonanoda" "$ROOT/profile.bin"
sha256sum "$ROOT/clean.bin" "$ROOT/profile.bin" > "$ROOT/binaries.sha256"
for corpus in std cedar mathlib; do
  input="$ROOT/arena/_build/tests/$corpus.ndjson"
  "$ROOT/clean.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/clean-$corpus.out"
  "$ROOT/profile.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/profile-$corpus.out"
  cmp "$ROOT/out/clean-$corpus.out" "$ROOT/out/profile-$corpus.out"
  echo "V83_${corpus^^}_REPLAY=EXACT"
done
# Sampling is observational. No kernel source or reduction semantics are changed.
# Use the pinned arena's Nix environment for perf; record permission failures explicitly.
cd "$ROOT/arena"
nix develop -c bash -c 'command -v perf; perf --version' > "$ROOT/perf-version.txt" 2>&1 || true
if ! command -v perf >/dev/null 2>&1; then
  PERF=$(nix develop -c sh -c 'command -v perf' 2>/dev/null || true)
else
  PERF=$(command -v perf)
fi
if [[ -z "$PERF" ]]; then
  echo 'DECISION=INFRASTRUCTURE_NO_PERF__NO_PROFILE_CLAIM' | tee "$ROOT/summary.txt"
  exit 2
fi
# A hosted runner may restrict perf_event_open. Try the unprivileged path first.
if ! "$PERF" record -q -e cpu-clock:u -F 99 -g --call-graph fp -o "$ROOT/probe.data" -- /bin/true > "$ROOT/probe.out" 2> "$ROOT/probe.err"; then
  if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    sudo -n sysctl -w kernel.perf_event_paranoid=1 >> "$ROOT/probe.err" 2>&1 || true
  fi
fi
if ! "$PERF" record -q -e cpu-clock:u -F 99 -g --call-graph fp -o "$ROOT/probe.data" -- /bin/true >> "$ROOT/probe.out" 2>> "$ROOT/probe.err"; then
  echo 'DECISION=INFRASTRUCTURE_PERF_DENIED__NO_PROFILE_CLAIM' | tee "$ROOT/summary.txt"
  exit 2
fi
printf 'corpus,repeat,event,samples\n' > "$ROOT/sample_counts.csv"
for corpus in std cedar mathlib; do
  repeats=1
  [[ "$corpus" == mathlib ]] && repeats=2
  for repeat in $(seq 1 "$repeats"); do
    input="$ROOT/arena/_build/tests/$corpus.ndjson"
    data="$ROOT/$corpus-$repeat.data"
    "$PERF" record -q -e cpu-clock:u -F 99 -g --call-graph fp -o "$data" -- "$ROOT/profile.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/sampled-$corpus-$repeat.out" 2> "$ROOT/out/sampled-$corpus-$repeat.err"
    cmp "$ROOT/out/clean-$corpus.out" "$ROOT/out/sampled-$corpus-$repeat.out"
    "$PERF" report -i "$data" --stdio --no-children --sort symbol,dso --percent-limit 0.2 > "$ROOT/$corpus-$repeat-report.txt"
    "$PERF" report -i "$data" --stdio --children --sort symbol,dso --percent-limit 0.5 > "$ROOT/$corpus-$repeat-children.txt"
    "$PERF" script -i "$data" > "$ROOT/$corpus-$repeat-stacks.txt"
    samples=$(grep -c '^sokonanoda ' "$ROOT/$corpus-$repeat-stacks.txt" || true)
    printf '%s,%s,cpu-clock:u,%s\n' "$corpus" "$repeat" "$samples" | tee -a "$ROOT/sample_counts.csv"
    echo "V83_${corpus^^}_${repeat}_SAMPLED_REPLAY=EXACT"
  done
done
python3 - "$ROOT" <<'PY' | tee "$ROOT/summary.txt"
import csv,sys
from pathlib import Path
root=Path(sys.argv[1])
rows=list(csv.DictReader(open(root/'sample_counts.csv')))
assert len(rows)==4 and all(int(r['samples'])>0 for r in rows), 'no usable CPU samples'
print('DECISION=BROAD_CPU_PROFILE_RECORDED__SELECT_MEASURED_COST_CENTER_NEXT')
print('SCOPE=FROZEN_STD_CEDAR_MATHLIB__CPU_SAMPLING_NOT_EXCLUSIVE_WALL_TIME')
print('NO_OPTIMIZATION_OR_SPEEDUP_CLAIM')
print('MATHLIB_REPEAT=2')
PY
