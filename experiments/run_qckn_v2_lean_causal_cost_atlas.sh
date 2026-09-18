#!/usr/bin/env bash
set -euo pipefail

ROOT=/tmp/qckn-v2-lean-causal-cost-atlas-v1
REPO=https://github.com/metalogiclabs/mathgraph-lean-kernel
ARENA_REPO=https://github.com/leanprover/lean-kernel-arena
ARENA_SHA=510fbfead6f02bed1a0179d01729a6ddf5bfd06d
CANDIDATE_SHA="${GITHUB_SHA:?GITHUB_SHA is required}"
WORKSPACE="${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
REALITYGRAPH_ROOT="${REALITYGRAPH_ROOT:?REALITYGRAPH_ROOT is required}"
PRIOR_AUTHORITY="$WORKSPACE/experiments/tests/fixtures/red-depth64-authority-run-35343216790.json"

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

cp "$PRIOR_AUTHORITY" "$ROOT/evidence/prior-red-authority.json"
{
  printf 'schema\tqckn-v2-lean-causal-cost-atlas-v1\n'
  printf 'candidate_sha\t%s\n' "$CANDIDATE_SHA"
  printf 'arena_sha\t%s\n' "$ARENA_SHA"
  printf 'realitygraph_sha\t%s\n' "$(git -C "$REALITYGRAPH_ROOT" rev-parse HEAD)"
  printf 'prior_red_run\t35343216790\n'
  printf 'prior_red_commit\t731da4ad2abf1461223a47620fbf584908cdec0f\n'
  printf 'source_workload\tperf/beta-ladder\n'
  printf 'arms\toff,0,8,32,64\n'
  printf 'cost_unit\tcallgrind-instructions\n'
  printf 'build\tPGO_x86_64_no_avx\n'
} > "$ROOT/evidence/provenance.tsv"

cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude
nix develop -c ./lka.py build-test perf/beta-ladder

prepare_arm() {
  local arm="$1"
  local dir="$ROOT/arm-$arm"
  git clone -q "$ROOT/source" "$dir"
  git -C "$dir" checkout -q "$CANDIDATE_SHA"

  grep -Fqx 'pub(crate) const R1_DIRECT_BETA_FUSION: bool = true;' "$dir/src/infer.rs"
  grep -Fqx 'pub(crate) const R1_MIN_DEPTH: u32 = 64;' "$dir/src/infer.rs"

  if [[ "$arm" == off ]]; then
    sed -i \
      's/pub(crate) const R1_DIRECT_BETA_FUSION: bool = true;/pub(crate) const R1_DIRECT_BETA_FUSION: bool = false;/' \
      "$dir/src/infer.rs"
  elif [[ "$arm" != 64 ]]; then
    sed -i \
      "s/pub(crate) const R1_MIN_DEPTH: u32 = 64;/pub(crate) const R1_MIN_DEPTH: u32 = $arm;/" \
      "$dir/src/infer.rs"
  fi

  git -C "$dir" diff -- src/infer.rs > "$ROOT/evidence/arm-$arm.patch"
}

build_arm() {
  local arm="$1"
  local dir="$ROOT/arm-$arm"
  local profile_cpu_flags
  profile_cpu_flags='-C target-cpu=x86-64 -C target-feature=-avx,-avx2,-avx512f,-fma'

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

for arm in off 0 8 32 64; do
  prepare_arm "$arm"
  build_arm "$arm"
done

VALGRIND=$(nix shell nixpkgs#valgrind -c sh -c 'command -v valgrind')
"$VALGRIND" --version | tee "$ROOT/evidence/valgrind-version.txt"
rustc --version --verbose > "$ROOT/evidence/rustc-version.txt"
cargo --version --verbose > "$ROOT/evidence/cargo-version.txt"
printf 'label\tarm\tstatus\tcallgrind_ir\tstdout_sha256\n' \
  > "$ROOT/evidence/measurements.tsv"

measure_arm() {
  local arm="$1"
  local input="$ROOT/arena/_build/tests/perf/beta-ladder.ndjson"
  local callgrind="$ROOT/beta-ladder.$arm.callgrind"
  local stdout="$ROOT/evidence/beta-ladder.$arm.stdout"
  local stderr="$ROOT/evidence/beta-ladder.$arm.stderr"
  local timing="$ROOT/evidence/beta-ladder.$arm.time"
  local status

  set +e
  /usr/bin/time -f 'wall_s=%e\nmax_rss_kb=%M' -o "$timing" \
    timeout 900s "$VALGRIND" --tool=callgrind --quiet \
      --callgrind-out-file="$callgrind" \
      "$ROOT/arm-$arm.bin" "$ROOT/config.json" \
      < "$input" > "$stdout" 2> "$stderr"
  status=$?
  set -e

  if [[ ! -s "$callgrind" ]]; then
    echo "missing Callgrind output for arm $arm" >&2
    sed -n '1,100p' "$stderr" >&2 || true
    return 1
  fi

  local ir
  local stdout_sha
  ir=$(awk '/^summary:/ {print $2; exit}' "$callgrind")
  stdout_sha=$(sha256sum "$stdout" | awk '{print $1}')
  if [[ -z "$ir" || "$ir" == 0 ]]; then
    echo "Callgrind instruction total unavailable for arm $arm" >&2
    return 1
  fi
  printf 'perf/beta-ladder\t%s\t%s\t%s\t%s\n' \
    "$arm" "$status" "$ir" "$stdout_sha" \
    | tee -a "$ROOT/evidence/measurements.tsv"
}

for arm in off 0 8 32 64; do
  measure_arm "$arm"
done

PYTHONPATH="$REALITYGRAPH_ROOT:$WORKSPACE" \
  python3 "$WORKSPACE/experiments/qckn_v2_lean_causal_cost_atlas.py" \
    --prior-authority-json "$PRIOR_AUTHORITY" \
    --measurements-tsv "$ROOT/evidence/measurements.tsv" \
    --output "$ROOT/evidence/qckn-v2-lean-causal-cost-atlas-result.json"

python3 -m json.tool \
  "$ROOT/evidence/qckn-v2-lean-causal-cost-atlas-result.json" \
  | tee "$ROOT/evidence/result.pretty.json"
