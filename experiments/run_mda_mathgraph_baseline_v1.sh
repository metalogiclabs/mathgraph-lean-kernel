#!/usr/bin/env bash
set -euo pipefail

BASE=d6a73279e6765e637f9741180cefbd7ef957d8e5
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/mda-mathgraph-baseline-v1
rm -rf "$ROOT"
mkdir -p "$ROOT/out" "$ROOT/evidence"

echo "MDA_BASELINE_HEAD=$(git rev-parse HEAD)"
echo "MDA_BASELINE_PRESENT=$BASE"
echo "MDA_BASELINE_ARENA=$ARENA"

git diff --exit-code "$BASE" -- Cargo.toml Cargo.lock src tests
echo "MDA_BASELINE_EXECUTABLE_PRESENT_UNCHANGED=PASS"

sha256sum   domains/lean-kernel/DOMAIN_CONTRACT.md   present/PRESENT.json   history/INTERACTION_REGISTRY.md   > "$ROOT/evidence/domain-file-sha256.txt"

{
  echo "mda_kernel_sha256=0fcf675ba073a61c7a3a406e9ac6153e8ead4d3ee41563ef8265c9641f20e90e"
  echo "mda_prompt_sha256=36ddc368c36d41b4fd4bc2bc3b1f00ed5d517e2efb81f9139f2f11d4ec970da5"
  echo "present_sha=$BASE"
  echo "arena_sha=$ARENA"
  rustc --version || true
  cargo --version || true
} > "$ROOT/evidence/freeze.txt"

grep -E "MemTotal|SwapTotal" /proc/meminfo > "$ROOT/evidence/host-meminfo.txt" || true

cargo test --release --locked -q
echo "MDA_BASELINE_SOURCE_TESTS=PASS"

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
for t in   init-prelude   extra-rec rec-missing-ih proj-of-stuck-prop proj-of-subst-prop   mathlib con-leche perf/app-lam perf/beta-ladder
do
  echo "MDA_BASELINE_BUILD_TEST=$t"
  nix develop -c ./lka.py build-test "$t" >/dev/null
done

cd "$GITHUB_WORKSPACE"
rm -rf "$ROOT/pgo"
RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$ROOT/pgo" cargo build --release --locked -q
target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null 2>/dev/null
cd "$ROOT/arena"
nix develop -c llvm-profdata merge -o "$ROOT/pgo/merged.profdata" "$ROOT/pgo"
cd "$GITHUB_WORKSPACE"
RUSTFLAGS="-C target-cpu=native -Cprofile-use=$ROOT/pgo/merged.profdata" cargo build --release --locked -q
echo "MDA_BASELINE_PGO=PASS"

: > "$ROOT/evidence/semantic-replay.tsv"
run_semantic () {
  local test="$1"
  local want="$2"
  local safe
  safe="$(printf '%s' "$test" | tr '/' '_')"
  local file="$ROOT/arena/_build/tests/$test.ndjson"
  set +e
  target/release/sokonanoda "$ROOT/config.json" < "$file" >"$ROOT/out/$safe.out" 2>"$ROOT/out/$safe.err"
  local rc=$?
  set -e
  printf '%s\twant=%s\trc=%s\n' "$test" "$want" "$rc" | tee -a "$ROOT/evidence/semantic-replay.tsv"
  [ "$rc" -eq "$want" ]
}

for t in extra-rec rec-missing-ih proj-of-stuck-prop proj-of-subst-prop; do
  run_semantic "$t" 1
done
for t in mathlib con-leche perf/app-lam perf/beta-ladder; do
  run_semantic "$t" 0
done
echo "MDA_BASELINE_SCREENING_SEMANTICS=PASS"

: > "$ROOT/evidence/measurements.tsv"
measure () {
  local test="$1"
  local safe
  safe="$(printf '%s' "$test" | tr '/' '_')"
  local tf="$ROOT/out/$safe.time"
  /usr/bin/time -f 'wall=%e\tuser=%U\tsys=%S\trss_kb=%M' -o "$tf"     target/release/sokonanoda "$ROOT/config.json"     < "$ROOT/arena/_build/tests/$test.ndjson" >/dev/null 2>"$ROOT/out/$safe.measure.err"
  printf '%s\t%s\n' "$test" "$(cat "$tf")" | tee -a "$ROOT/evidence/measurements.tsv"
}
measure mathlib
measure con-leche
measure perf/app-lam
measure perf/beta-ladder

set +e
perf stat -e instructions true >/dev/null 2>"$ROOT/out/perf-probe.txt"
perf_rc=$?
set -e
if [ "$perf_rc" -eq 0 ]; then
  echo "instructions_local=available" > "$ROOT/evidence/instruction-authority.txt"
else
  echo "instructions_local=unavailable" > "$ROOT/evidence/instruction-authority.txt"
  cat "$ROOT/out/perf-probe.txt" >> "$ROOT/evidence/instruction-authority.txt"
fi

python3 - "$ROOT" <<'PY'
import json, pathlib, sys
root=pathlib.Path(sys.argv[1])
semantic=[]
for line in (root/"evidence/semantic-replay.tsv").read_text().splitlines():
    parts=line.split("\t")
    semantic.append({"test":parts[0], "want":int(parts[1].split("=")[1]), "rc":int(parts[2].split("=")[1])})
measure=[]
for line in (root/"evidence/measurements.tsv").read_text().splitlines():
    p=line.split("\t")
    row={"test":p[0]}
    for x in p[1:]:
        k,v=x.split("=",1); row[k]=float(v) if k!="rss_kb" else int(v)
    measure.append(row)
instruction=(root/"evidence/instruction-authority.txt").read_text(errors="replace").splitlines()[0].split("=",1)[1]
data={
  "schema":"mda-baseline-v1",
  "present_sha":"d6a73279e6765e637f9741180cefbd7ef957d8e5",
  "arena_sha":"ac1c13762de41b594fa24b90ede8cfd97ac6a765",
  "screening_semantic_replay":semantic,
  "measurements":measure,
  "local_retired_instruction_counter":instruction,
  "claim_boundary":{
    "semantic":"screening replay only; full pinned Arena replay required for promotion",
    "performance":"hosted timing is descriptive; Arena-ranked Mathlib win requires authoritative instruction measurement"
  }
}
(root/"evidence/baseline.json").write_text(json.dumps(data,indent=2)+"\n")
PY

echo "MDA_BASELINE_COMPLETE=PASS"
