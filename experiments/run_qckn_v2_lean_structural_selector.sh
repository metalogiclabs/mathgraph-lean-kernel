#!/usr/bin/env bash
set -euo pipefail

ROOT=/tmp/qckn-v2-lean-shallow-structural-selector-v1
REPO=https://github.com/metalogiclabs/mathgraph-lean-kernel
ARENA_REPO=https://github.com/leanprover/lean-kernel-arena
ARENA_SHA=510fbfead6f02bed1a0179d01729a6ddf5bfd06d
CANDIDATE_SHA="${GITHUB_SHA:?GITHUB_SHA is required}"
WORKSPACE="${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
REALITYGRAPH_ROOT="${REALITYGRAPH_ROOT:?REALITYGRAPH_ROOT is required}"

rm -rf -- "$ROOT"
mkdir -p "$ROOT/evidence"
git clone -q "$REPO" "$ROOT/source"
git -C "$ROOT/source" checkout -q "$CANDIDATE_SHA"
git clone -q "$ARENA_REPO" "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA_SHA"
test "$(git -C "$ROOT/arena" rev-parse HEAD)" = "$ARENA_SHA"

printf '%s\n' \
  '{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}' \
  > "$ROOT/config.json"

{
  printf 'schema\tqckn-v2-lean-shallow-structural-selector-v1\n'
  printf 'candidate_sha\t%s\n' "$CANDIDATE_SHA"
  printf 'arena_sha\t%s\n' "$ARENA_SHA"
  printf 'realitygraph_sha\t%s\n' "$(git -C "$REALITYGRAPH_ROOT" rev-parse HEAD)"
  printf 'prior_atlas_run\t35378475530\n'
  printf 'prior_atlas_commit\t065e12d1f0e453351e515749b4737925af741522\n'
  printf 'selector_family\tconsecutive-recurrent-beta-chain-length\n'
  printf 'selector_portfolio\t2,4,8\n'
  printf 'selector_scope\tdepth_0_through_7_only__depth_8_plus_retained\n'
  printf 'selection_rule\tmax_threshold_retaining_gte_0.90_of_incremental_shallow_savings\n'
  printf 'cost_unit\tcallgrind-instructions\n'
  printf 'search_cost_unit\tstructural-candidate-inspected\n'
  printf 'build\tPGO_x86_64_no_avx\n'
} > "$ROOT/evidence/provenance.tsv"

cd "$ROOT/arena"
for workload in \
  init-prelude \
  perf/beta-ladder \
  perf/magma-list-deep-n21 \
  perf/grind-ring-5 \
  mathlib
do
  nix develop -c ./lka.py build-test "$workload"
done

prepare_arm() {
  local arm="$1"
  local dir="$ROOT/arm-$arm"
  git clone -q "$ROOT/source" "$dir"
  git -C "$dir" checkout -q "$CANDIDATE_SHA"
  grep -Fqx 'pub(crate) const R1_DIRECT_BETA_FUSION: bool = true;' "$dir/src/infer.rs"
  grep -Fqx 'pub(crate) const R1_MIN_DEPTH: u32 = 0;' "$dir/src/infer.rs"
  grep -Fqx 'pub(crate) const R1_MIN_RECURRENT_CHAIN: u16 = 8;' "$dir/src/infer.rs"
  if [[ "$arm" == off ]]; then
    sed -i \
      's/pub(crate) const R1_DIRECT_BETA_FUSION: bool = true;/pub(crate) const R1_DIRECT_BETA_FUSION: bool = false;/' \
      "$dir/src/infer.rs"
  elif [[ "$arm" == base8 ]]; then
    sed -i \
      's/pub(crate) const R1_MIN_DEPTH: u32 = 0;/pub(crate) const R1_MIN_DEPTH: u32 = 8;/' \
      "$dir/src/infer.rs"
  else
    local threshold="${arm#chain}"
    sed -i \
      "s/pub(crate) const R1_MIN_RECURRENT_CHAIN: u16 = 8;/pub(crate) const R1_MIN_RECURRENT_CHAIN: u16 = $threshold;/" \
      "$dir/src/infer.rs"
  fi
  git -C "$dir" diff -- src/infer.rs > "$ROOT/evidence/arm-$arm.patch"
}

build_arm() {
  local arm="$1"
  local dir="$ROOT/arm-$arm"
  local profile_cpu_flags='-C target-cpu=x86-64 -C target-feature=-avx,-avx2,-avx512f,-fma'
  rm -rf -- "$dir/pgo"
  mkdir -p "$dir/pgo"
  (
    cd "$dir"
    RUSTFLAGS="$profile_cpu_flags -Cprofile-generate=$dir/pgo" \
      cargo build --release --locked
    target/release/sokonanoda "$ROOT/config.json" \
      < "$ROOT/arena/_build/tests/init-prelude.ndjson" > /dev/null
    nix shell nixpkgs#llvmPackages_21.llvm -c \
      llvm-profdata merge -o "$dir/pgo/merged.profdata" "$dir/pgo"
    test -s "$dir/pgo/merged.profdata"
    RUSTFLAGS="$profile_cpu_flags -Cprofile-use=$dir/pgo/merged.profdata" \
      cargo build --release --locked
  )
  cp "$dir/target/release/sokonanoda" "$ROOT/arm-$arm.bin"
  sha256sum "$ROOT/arm-$arm.bin" >> "$ROOT/evidence/binaries.sha256"
}

for arm in off base8 chain2 chain4 chain8; do
  prepare_arm "$arm"
  build_arm "$arm"
done

VALGRIND=$(nix shell nixpkgs#valgrind -c sh -c 'command -v valgrind')
"$VALGRIND" --version | tee "$ROOT/evidence/valgrind-version.txt"
rustc --version --verbose > "$ROOT/evidence/rustc-version.txt"
cargo --version --verbose > "$ROOT/evidence/cargo-version.txt"
printf 'label\tarm\tstatus\tcallgrind_ir\tstdout_sha256\n' \
  > "$ROOT/evidence/measurements.tsv"

measure_one() {
  local label="$1"
  local arm="$2"
  local limit="$3"
  local input="$ROOT/arena/_build/tests/$label.ndjson"
  local stem="${label//\//_}.$arm"
  local callgrind="$ROOT/$stem.callgrind"
  local stdout="$ROOT/evidence/$stem.stdout"
  local stderr="$ROOT/evidence/$stem.stderr"
  local timing="$ROOT/evidence/$stem.time"
  local status
  set +e
  /usr/bin/time -f 'wall_s=%e\nmax_rss_kb=%M' -o "$timing" \
    timeout "$limit" "$VALGRIND" --tool=callgrind --quiet \
      --callgrind-out-file="$callgrind" \
      "$ROOT/arm-$arm.bin" "$ROOT/config.json" \
      < "$input" > "$stdout" 2> "$stderr"
  status=$?
  set -e
  test -s "$callgrind"
  local ir
  local stdout_sha
  ir=$(awk '/^summary:/ {print $2; exit}' "$callgrind")
  stdout_sha=$(sha256sum "$stdout" | awk '{print $1}')
  test -n "$ir"
  test "$ir" != 0
  printf '%s\t%s\t%s\t%s\t%s\n' \
    "$label" "$arm" "$status" "$ir" "$stdout_sha" \
    | tee -a "$ROOT/evidence/measurements.tsv"
}

for arm in base8 chain2 chain4 chain8; do
  measure_one perf/beta-ladder "$arm" 900s
done

SELECTED_ARM=$(python3 - "$ROOT/evidence/measurements.tsv" <<'PY'
import csv, sys
rows=list(csv.DictReader(open(sys.argv[1]), delimiter="\t"))
by={row["arm"]:row for row in rows if row["label"]=="perf/beta-ladder"}
base=by["base8"]
unrestricted=by["chain2"]
if int(base["status"]) != 0 or int(unrestricted["status"]) != 0:
    raise SystemExit("SHALLOW_DISCOVERY_ARM_DID_NOT_ACCEPT")
if base["stdout_sha256"] != unrestricted["stdout_sha256"]:
    raise SystemExit("SHALLOW_DISCOVERY_PARITY_FAILED")
total=int(base["callgrind_ir"])-int(unrestricted["callgrind_ir"])
qualified=[]
for arm in ("chain2","chain4","chain8"):
    row=by[arm]
    parity=int(row["status"])==0 and row["stdout_sha256"]==base["stdout_sha256"]
    retained=(int(base["callgrind_ir"])-int(row["callgrind_ir"]))/total if total > 0 else 0.0
    if parity and retained >= 0.90:
        qualified.append(arm)
print(qualified[-1] if qualified else "none")
PY
)
printf 'selected_arm\t%s\n' "$SELECTED_ARM" >> "$ROOT/evidence/provenance.tsv"

if [[ "$SELECTED_ARM" != none ]]; then
  measure_one perf/beta-ladder off 900s
  for label in perf/magma-list-deep-n21 perf/grind-ring-5 mathlib; do
    case "$label" in
      mathlib) limit=7200s ;;
      perf/grind-ring-5) limit=1800s ;;
      *) limit=900s ;;
    esac
    measure_one "$label" off "$limit"
    measure_one "$label" "$SELECTED_ARM" "$limit"
  done
fi

PYTHONPATH="$REALITYGRAPH_ROOT:$WORKSPACE" \
  python3 "$WORKSPACE/experiments/qckn_v2_lean_structural_selector.py" \
    --measurements-tsv "$ROOT/evidence/measurements.tsv" \
    --output "$ROOT/evidence/qckn-v2-lean-structural-selector-result.json"

python3 -m json.tool \
  "$ROOT/evidence/qckn-v2-lean-structural-selector-result.json" \
  | tee "$ROOT/evidence/result.pretty.json"
