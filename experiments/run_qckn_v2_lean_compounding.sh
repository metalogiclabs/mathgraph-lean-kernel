#!/usr/bin/env bash
set -euo pipefail

ROOT=/tmp/qckn-v2-lean-compounding-falsification-v1
REPO=https://github.com/metalogiclabs/mathgraph-lean-kernel
ARENA_REPO=https://github.com/leanprover/lean-kernel-arena
ARENA_SHA=510fbfead6f02bed1a0179d01729a6ddf5bfd06d
CANDIDATE_SHA="${GITHUB_SHA:?GITHUB_SHA is required}"
REALITYGRAPH_ROOT="${REALITYGRAPH_ROOT:?REALITYGRAPH_ROOT is required}"

rm -rf -- "$ROOT"
mkdir -p "$ROOT/evidence"

git clone -q "$REPO" "$ROOT/candidate"
git -C "$ROOT/candidate" checkout -q "$CANDIDATE_SHA"
git clone -q "$REPO" "$ROOT/ablated"
git -C "$ROOT/ablated" checkout -q "$CANDIDATE_SHA"

ABLATION_PATTERN='pub(crate) const R1_DIRECT_BETA_FUSION: bool = true;'
grep -Fqx "$ABLATION_PATTERN" "$ROOT/ablated/src/infer.rs"
sed -i \
  's/pub(crate) const R1_DIRECT_BETA_FUSION: bool = true;/pub(crate) const R1_DIRECT_BETA_FUSION: bool = false;/' \
  "$ROOT/ablated/src/infer.rs"
git -C "$ROOT/ablated" diff --exit-code --quiet && {
  echo 'exact R1 ablation produced no source change' >&2
  exit 1
}
git -C "$ROOT/ablated" diff -- src/infer.rs > "$ROOT/evidence/exact-r1-ablation.patch"

git clone -q "$ARENA_REPO" "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA_SHA"
ACTUAL_ARENA_SHA=$(git -C "$ROOT/arena" rev-parse HEAD)
test "$ACTUAL_ARENA_SHA" = "$ARENA_SHA"

printf '%s\n' \
  '{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}' \
  > "$ROOT/config.json"

{
  printf 'candidate_sha\t%s\n' "$CANDIDATE_SHA"
  printf 'arena_sha\t%s\n' "$ARENA_SHA"
  printf 'realitygraph_sha\t%s\n' "$(git -C "$REALITYGRAPH_ROOT" rev-parse HEAD)"
  printf 'counter\tcallgrind_Ir\n'
  printf 'build\tPGO_x86_64_no_avx\n'
  printf 'ablation\tR1_DIRECT_BETA_FUSION=false\n'
  printf 'selector_portfolio\t0,8,32,64\n'
  printf 'search_cost_unit\tselector-candidate-inspected\n'
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

build_arm() {
  local arm="$1"
  local dir="$ROOT/$arm"
  rm -rf -- "$dir/pgo"
  mkdir -p "$dir/pgo"
  (
    cd "$dir"
    local profile_cpu_flags
    profile_cpu_flags='-C target-cpu=x86-64 -C target-feature=-avx,-avx2,-avx512f,-fma'
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
  cp "$dir/target/release/sokonanoda" "$ROOT/$arm.bin"
  sha256sum "$ROOT/$arm.bin" >> "$ROOT/evidence/binaries.sha256"
}

build_arm ablated
build_arm candidate

VALGRIND=$(nix shell nixpkgs#valgrind -c sh -c 'command -v valgrind')
"$VALGRIND" --version | tee "$ROOT/evidence/valgrind-version.txt"
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
      "$ROOT/$arm.bin" "$ROOT/config.json" \
      < "$input" > "$stdout" 2> "$stderr"
  status=$?
  set -e

  if [[ ! -s "$callgrind" ]]; then
    echo "missing Callgrind output for $label/$arm" >&2
    sed -n '1,100p' "$stderr" >&2 || true
    return 1
  fi

  local ir
  local stdout_sha
  ir=$(awk '/^summary:/ {print $2; exit}' "$callgrind")
  stdout_sha=$(sha256sum "$stdout" | awk '{print $1}')
  if [[ -z "$ir" || "$ir" == 0 ]]; then
    echo "Callgrind instruction total unavailable for $label/$arm" >&2
    return 1
  fi
  printf '%s\t%s\t%s\t%s\t%s\n' \
    "$label" "$arm" "$status" "$ir" "$stdout_sha" \
    | tee -a "$ROOT/evidence/measurements.tsv"
}

for arm in ablated candidate; do
  measure_one perf/beta-ladder "$arm" 900s
  measure_one perf/magma-list-deep-n21 "$arm" 900s
  measure_one perf/grind-ring-5 "$arm" 1800s
  measure_one mathlib "$arm" 7200s
done

python3 - \
  "$ROOT/evidence/measurements.tsv" \
  "$ROOT/evidence/authority.json" \
  "$CANDIDATE_SHA" \
  "$ARENA_SHA" <<'PY'
import csv
import json
import sys
from pathlib import Path

measurements_path, output_path, candidate_sha, arena_sha = sys.argv[1:]
rows = list(csv.DictReader(open(measurements_path), delimiter="\t"))
by = {(row["label"], row["arm"]): row for row in rows}
labels = (
    "perf/beta-ladder",
    "perf/magma-list-deep-n21",
    "perf/grind-ring-5",
    "mathlib",
)
workloads = {}
for label in labels:
    ablated = by[(label, "ablated")]
    candidate = by[(label, "candidate")]
    ablated_status = int(ablated["status"])
    candidate_status = int(candidate["status"])
    parity = (
        ablated_status == candidate_status
        and ablated["stdout_sha256"] == candidate["stdout_sha256"]
    )
    if ablated_status != 0 or candidate_status != 0:
        raise SystemExit(
            f"AUTHORITY_REJECTED: {label} did not accept "
            f"(ablated={ablated_status}, candidate={candidate_status})"
        )
    workloads[label] = {
        "parity": parity,
        "ablated_ir": int(ablated["callgrind_ir"]),
        "candidate_ir": int(candidate["callgrind_ir"]),
    }

payload = {
    "schema": "qckn-v2-lean-authority-v1",
    "candidate_sha": candidate_sha,
    "arena_sha": arena_sha,
    "authority_snapshot": f"lean-kernel-arena@{arena_sha}+candidate@{candidate_sha}",
    "verifier_id": "lean-kernel-arena-callgrind-exact-ablation-v1",
    "workloads": workloads,
}
Path(output_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
PY

PYTHONPATH="$REALITYGRAPH_ROOT:${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}" \
  python3 "$GITHUB_WORKSPACE/experiments/qckn_v2_lean_compounding.py" \
    --authority-json "$ROOT/evidence/authority.json" \
    --output "$ROOT/evidence/qckn-v2-lean-compounding-result.json"

python3 -m json.tool \
  "$ROOT/evidence/qckn-v2-lean-compounding-result.json" \
  | tee "$ROOT/evidence/result.pretty.json"
