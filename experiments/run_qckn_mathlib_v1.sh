#!/usr/bin/env bash
set -euo pipefail

LEADER_SHA=28c03d0103e004610e4d47a4828965efb2b70af9
ROOT=/tmp/qckn-mathlib-v1
REPO=https://github.com/metalogiclabs/mathgraph-lean-kernel
ARENA_REPO=https://github.com/leanprover/lean-kernel-arena
CANDIDATE_SHA="${GITHUB_SHA:?GITHUB_SHA is required}"

rm -rf "$ROOT"
mkdir -p "$ROOT/evidence"

git clone -q "$REPO" "$ROOT/leader"
git -C "$ROOT/leader" checkout -q "$LEADER_SHA"
git clone -q "$REPO" "$ROOT/candidate"
git -C "$ROOT/candidate" checkout -q "$CANDIDATE_SHA"
git clone -q --depth 1 "$ARENA_REPO" "$ROOT/arena"
ARENA_SHA=$(git -C "$ROOT/arena" rev-parse HEAD)

cat >"$ROOT/evidence/provenance.tsv" <<EOF
leader_sha	$LEADER_SHA
candidate_sha	$CANDIDATE_SHA
arena_sha	$ARENA_SHA
EOF

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude
nix develop -c ./lka.py build-test perf/beta-ladder

build_arm() {
  local arm="$1"
  local dir="$ROOT/$arm"
  rm -rf "$dir/pgo"
  mkdir -p "$dir/pgo"
  (
    cd "$dir"
    RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$dir/pgo" cargo build --release --locked
    target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
    nix shell nixpkgs#llvmPackages_21.llvm -c llvm-profdata merge -o "$dir/pgo/merged.profdata" "$dir/pgo"
    test -s "$dir/pgo/merged.profdata"
    RUSTFLAGS="-C target-cpu=native -Cprofile-use=$dir/pgo/merged.profdata" cargo build --release --locked
  )
  cp "$dir/target/release/sokonanoda" "$ROOT/$arm.bin"
  sha256sum "$ROOT/$arm.bin" >> "$ROOT/evidence/binaries.sha256"
}

build_arm leader
build_arm candidate

PERF=$(command -v perf || true)
if [[ -z "$PERF" ]]; then
  PERF=$(cd "$ROOT/arena" && nix develop -c sh -c 'command -v perf')
fi
"$PERF" --version | tee "$ROOT/evidence/perf-version.txt"

printf 'label	arm	rep	status	instructions
' > "$ROOT/evidence/measurements.tsv"

measure_one() {
  local label="$1"
  local arm="$2"
  local rep="$3"
  local input="$4"
  local perfout="$ROOT/evidence/${label//\//_}.$arm.$rep.perf.json"
  local stdout="$ROOT/evidence/${label//\//_}.$arm.$rep.stdout"
  local stderr="$ROOT/evidence/${label//\//_}.$arm.$rep.stderr"
  set +e
  LC_ALL=C "$PERF" stat -j -o "$perfout" \
    -e duration_time -e task-clock -e instructions -- \
    "$ROOT/$arm.bin" "$ROOT/config.json" < "$input" > "$stdout" 2> "$stderr"
  local status=$?
  set -e
  local instructions
  instructions=$(python3 - "$perfout" <<'PY'
import json,sys
path=sys.argv[1]
found=None
for raw in open(path, errors='replace'):
    raw=raw.strip()
    if not raw:
        continue
    try:
        row=json.loads(raw)
    except json.JSONDecodeError:
        continue
    event=str(row.get("event","")).split(":")[0]
    if event != "instructions":
        continue
    value=row.get("counter-value")
    try:
        found=int(float(value))
    except (TypeError,ValueError):
        pass
if not found:
    raise SystemExit("instruction counter unavailable")
print(found)
PY
)
  printf '%s	%s	%s	%s	%s
' "$label" "$arm" "$rep" "$status" "$instructions" | tee -a "$ROOT/evidence/measurements.tsv"
}

for arm in leader candidate; do
  for rep in 1 2 3; do
    measure_one perf/beta-ladder "$arm" "$rep" "$ROOT/arena/_build/tests/perf/beta-ladder.ndjson"
  done
done

python3 - "$ROOT/evidence/measurements.tsv" <<'PY' | tee "$ROOT/evidence/beta-scorecard.txt"
import csv,statistics,sys
rows=list(csv.DictReader(open(sys.argv[1]), delimiter="\t"))
by={}
for r in rows:
    by.setdefault((r["label"],r["arm"]),[]).append(r)
for arm in ("leader","candidate"):
    rs=by[("perf/beta-ladder",arm)]
    assert len(rs)==3
    assert all(int(r["status"])==0 for r in rs), f"{arm} beta-ladder did not accept"
li=statistics.median(int(r["instructions"]) for r in by[("perf/beta-ladder","leader")])
ci=statistics.median(int(r["instructions"]) for r in by[("perf/beta-ladder","candidate")])
speed=li/ci
print(f"leader_beta_instructions={li}")
print(f"candidate_beta_instructions={ci}")
print(f"beta_instruction_speedup={speed:.6f}")
assert speed >= 2.0, f"RED: no >=2x causal beta capability yet ({speed:.6f}x)"
print("QCKN_BETA_CAPABILITY_PASS")
PY

# Only a candidate that first proves the causal capability earns the expensive
# protected-consequence measurements.
cd "$ROOT/arena"
nix develop -c ./lka.py build-test perf/grind-ring-5
nix develop -c ./lka.py build-test mathlib

for label in perf/grind-ring-5 mathlib; do
  input="$ROOT/arena/_build/tests/$label.ndjson"
  reps=3
  [[ "$label" == mathlib ]] && reps=2
  for arm in leader candidate; do
    for rep in $(seq 1 "$reps"); do
      measure_one "$label" "$arm" "$rep" "$input"
    done
  done
done

python3 - "$ROOT/evidence/measurements.tsv" <<'PY' | tee "$ROOT/evidence/promotion-scorecard.txt"
import csv,statistics,sys
rows=list(csv.DictReader(open(sys.argv[1]), delimiter="\t"))
by={}
for r in rows:
    by.setdefault((r["label"],r["arm"]),[]).append(r)

def med(label,arm):
    rs=by[(label,arm)]
    assert rs and all(int(r["status"])==0 for r in rs), f"{label}/{arm} did not accept"
    return statistics.median(int(r["instructions"]) for r in rs)

for label in ("perf/beta-ladder","perf/grind-ring-5","mathlib"):
    l=med(label,"leader"); c=med(label,"candidate"); s=l/c
    print(f"{label}\tleader={l}\tcandidate={c}\tspeedup={s:.6f}")

beta=med("perf/beta-ladder","leader")/med("perf/beta-ladder","candidate")
grind=med("perf/grind-ring-5","leader")/med("perf/grind-ring-5","candidate")
mathlib=med("mathlib","leader")/med("mathlib","candidate")
assert beta >= 2.0, "causal beta capability disappeared"
assert grind >= 0.95, f"protected grind regression exceeds 5% ({grind:.6f}x)"
assert mathlib >= 1.001, f"Mathlib instructions did not improve by at least 0.1% ({mathlib:.6f}x)"
print("QCKN_MATHLIB_PROMOTION_PASS")
PY
