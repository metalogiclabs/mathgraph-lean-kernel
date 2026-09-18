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
development_counter	callgrind_Ir
final_counter	Arena_perf_retired_instructions
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

VALGRIND=$(nix shell nixpkgs#valgrind -c sh -c 'command -v valgrind')
"$VALGRIND" --version | tee "$ROOT/evidence/valgrind-version.txt"
printf 'label	arm	rep	status	callgrind_ir
' > "$ROOT/evidence/measurements.tsv"

measure_one() {
  local label="$1"
  local arm="$2"
  local rep="$3"
  local input="$4"
  local limit="$5"
  local stem="${label//\//_}.$arm.$rep"
  local cg="$ROOT/evidence/$stem.callgrind"
  local stdout="$ROOT/evidence/$stem.stdout"
  local stderr="$ROOT/evidence/$stem.stderr"
  local timing="$ROOT/evidence/$stem.time"
  set +e
  /usr/bin/time -f 'wall_s=%e\nmax_rss_kb=%M' -o "$timing" \
    timeout "$limit" "$VALGRIND" --tool=callgrind --quiet \
      --callgrind-out-file="$cg" \
      "$ROOT/$arm.bin" "$ROOT/config.json" < "$input" > "$stdout" 2> "$stderr"
  local status=$?
  set -e
  if [[ ! -s "$cg" ]]; then
    echo "missing Callgrind output for $label/$arm/$rep" >&2
    cat "$stderr" >&2 || true
    return 1
  fi
  local ir
  ir=$(awk '/^summary:/ {print $2; exit}' "$cg")
  if [[ -z "$ir" || "$ir" == "0" ]]; then
    echo "Callgrind instruction total unavailable for $label/$arm/$rep" >&2
    head -100 "$cg" >&2 || true
    return 1
  fi
  printf '%s	%s	%s	%s	%s
' "$label" "$arm" "$rep" "$status" "$ir" | tee -a "$ROOT/evidence/measurements.tsv"
}

# RED/GREEN causal witness. Callgrind Ir is deterministic enough that one run
# per exact PGO binary is preferable to noisy wall-time repetition.
for arm in leader candidate; do
  measure_one perf/beta-ladder "$arm" 1 "$ROOT/arena/_build/tests/perf/beta-ladder.ndjson" 900s
done

python3 - "$ROOT/evidence/measurements.tsv" <<'PY' | tee "$ROOT/evidence/beta-scorecard.txt"
import csv,sys
rows=list(csv.DictReader(open(sys.argv[1]), delimiter="\t"))
by={(r["label"],r["arm"]):r for r in rows}
for arm in ("leader","candidate"):
    r=by[("perf/beta-ladder",arm)]
    assert int(r["status"]) == 0, f"{arm} beta-ladder did not accept"
li=int(by[("perf/beta-ladder","leader")]["callgrind_ir"])
ci=int(by[("perf/beta-ladder","candidate")]["callgrind_ir"])
speed=li/ci
print("counter=callgrind_Ir_development_proxy")
print(f"leader_beta_ir={li}")
print(f"candidate_beta_ir={ci}")
print(f"beta_ir_speedup={speed:.6f}")
assert speed >= 2.0, f"RED: no >=2x causal beta capability yet ({speed:.6f}x)"
print("QCKN_BETA_CAPABILITY_PASS")
PY

# A capability that cannot beat its causal witness never earns the expensive
# protected-consequence measurements.
cd "$ROOT/arena"
nix develop -c ./lka.py build-test perf/grind-ring-5
nix develop -c ./lka.py build-test mathlib

for arm in leader candidate; do
  measure_one perf/grind-ring-5 "$arm" 1 "$ROOT/arena/_build/tests/perf/grind-ring-5.ndjson" 1800s
done
for arm in leader candidate; do
  measure_one mathlib "$arm" 1 "$ROOT/arena/_build/tests/mathlib.ndjson" 5400s
done

python3 - "$ROOT/evidence/measurements.tsv" <<'PY' | tee "$ROOT/evidence/promotion-scorecard.txt"
import csv,sys
rows=list(csv.DictReader(open(sys.argv[1]), delimiter="\t"))
by={(r["label"],r["arm"]):r for r in rows}

def ir(label,arm):
    r=by[(label,arm)]
    assert int(r["status"]) == 0, f"{label}/{arm} did not accept"
    return int(r["callgrind_ir"])

for label in ("perf/beta-ladder","perf/grind-ring-5","mathlib"):
    l=ir(label,"leader"); c=ir(label,"candidate"); s=l/c
    print(f"{label}\tleader_ir={l}\tcandidate_ir={c}\tspeedup={s:.6f}")

beta=ir("perf/beta-ladder","leader")/ir("perf/beta-ladder","candidate")
grind=ir("perf/grind-ring-5","leader")/ir("perf/grind-ring-5","candidate")
mathlib=ir("mathlib","leader")/ir("mathlib","candidate")
assert beta >= 2.0, "causal beta capability disappeared"
assert grind >= 0.95, f"protected grind proxy regression exceeds 5% ({grind:.6f}x)"
assert mathlib >= 1.001, f"Mathlib development proxy did not improve by at least 0.1% ({mathlib:.6f}x)"
print("QCKN_MATHLIB_DEVELOPMENT_PROXY_PASS")
print("FINAL_EXACT_ARENA_INSTRUCTION_GATE_REQUIRED")
PY
