#!/usr/bin/env bash
set -euo pipefail

BASE=c6d445a954def8922490d0cd874ea134b45463dd
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/mda-auto-materialize-v2
TRAIN=(con-leche perf/app-lam perf/beta-ladder perf/let-ladder)

SELECTED="$(tr -d '[:space:]' < mda/AUTONOMOUS_CHECKER_GENESIS_V2_SELECTED)"
test -n "$SELECTED"
echo "MDA_V2_MATERIALIZE_LABEL=$SELECTED"

git diff --quiet "$BASE" -- src/eval.rs src/main.rs
rm -rf "$ROOT"
mkdir -p "$ROOT/census" "$ROOT/policies" mda/generated/autonomous_cache_admission_v2
cp src/eval.rs "$ROOT/clean-eval.rs"
cp src/main.rs "$ROOT/clean-main.rs"

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
cd "$ROOT/arena"
for t in "${TRAIN[@]}"; do
  nix develop -c ./lka.py build-test "$t" >/dev/null
done
cd "$GITHUB_WORKSPACE"

python3 scripts/mda_autonomous_cache_genesis_v2.py instrument src/eval.rs src/main.rs
RUSTFLAGS="-C target-cpu=native" cargo build --release --locked -q
for t in "${TRAIN[@]}"; do
  safe="$(printf '%s' "$t" | tr '/' '_')"
  MDA_V2_CACHE_CENSUS=1 target/release/sokonanoda "$ROOT/config.json"     < "$ROOT/arena/_build/tests/$t.ndjson" > /dev/null 2> "$ROOT/census/$safe.stderr"
done

python3 scripts/mda_autonomous_cache_genesis_v2.py parse-census   "$ROOT/training-census.json" "$ROOT"/census/*.stderr
python3 scripts/mda_autonomous_cache_genesis_v2.py make-policies   "$ROOT/training-census.json" "$ROOT/policies"

test -f "$ROOT/policies/$SELECTED.json"
cp "$ROOT/clean-main.rs" src/main.rs
python3 scripts/mda_autonomous_cache_genesis_v2.py apply-policy   "$ROOT/clean-eval.rs" "$ROOT/policies/$SELECTED.json" src/eval.rs
cargo test --release --locked -q

cp "$ROOT/training-census.json" mda/generated/autonomous_cache_admission_v2/
cp "$ROOT/policies/$SELECTED.json" mda/generated/autonomous_cache_admission_v2/selected-policy.json
printf '%s\n' "$BASE" > mda/generated/autonomous_cache_admission_v2/base-sha.txt
printf '%s\n' "$SELECTED" > mda/generated/autonomous_cache_admission_v2/selected-label.txt

git config user.name "mathgraph-developmental-ci"
git config user.email "actions@users.noreply.github.com"
git add src/eval.rs mda/generated/autonomous_cache_admission_v2/
git commit -m "Generate autonomous cache admission mechanism v2"
CANDIDATE="$(git rev-parse HEAD)"
echo "MDA_V2_MATERIALIZED_SHA=$CANDIDATE"
git push origin HEAD:refs/heads/candidate/autonomous-cache-admission-v2 --force
