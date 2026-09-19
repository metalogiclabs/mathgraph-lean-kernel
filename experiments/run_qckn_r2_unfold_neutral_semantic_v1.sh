#!/usr/bin/env bash
set -euo pipefail

ARENA_SHA=510fbfead6f02bed1a0179d01729a6ddf5bfd06d
ROOT=/tmp/qckn-r2-unfold-neutral-semantic-v1
ARENA_REPO=https://github.com/leanprover/lean-kernel-arena
SOURCE_SHA="${GITHUB_SHA:?GITHUB_SHA required}"

rm -rf "$ROOT"
mkdir -p "$ROOT/evidence"

git worktree add "$ROOT/candidate" "$SOURCE_SHA"
cp -a "$ROOT/candidate" "$ROOT/ablated"
python3 - "$ROOT/ablated/src/eval.rs" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
old='pub(crate) const EVAL_PLAIN_UNFOLD_NEUTRAL_FAST: bool = true;'
new='pub(crate) const EVAL_PLAIN_UNFOLD_NEUTRAL_FAST: bool = false;'
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY

(
  cd "$ROOT/candidate"
  cargo test --release --locked qckn_r2_unfold_neutral_tests -- --nocapture
)
for arm in candidate ablated; do
  (
    cd "$ROOT/$arm"
    RUSTFLAGS='-C target-cpu=x86-64-v3' cargo build --release --locked
    cp target/release/sokonanoda "$ROOT/$arm.bin"
  )
done

git clone -q "$ARENA_REPO" "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA_SHA"
cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}
EOF

cd "$ROOT/arena"
: > "$ROOT/evidence/build-tests.tsv"
while IFS= read -r y; do
  t=${y#tests/}; t=${t%.yaml}
  printf 'BUILD\t%s\n' "$t" | tee -a "$ROOT/evidence/build-tests.tsv"
  nix develop -c ./lka.py build-test "$t" >> "$ROOT/evidence/build-tests.tsv" 2>&1
done < <(find tests -type f -name '*.yaml' | sort)
find _build/tests -type f -name '*.ndjson' | sort > "$ROOT/evidence/built-exports.txt"
test -s "$ROOT/evidence/built-exports.txt"

: > "$ROOT/evidence/semantic-mismatches.tsv"
: > "$ROOT/evidence/correctness.tsv"
while IFS= read -r f; do
  set +e
  "$ROOT/ablated.bin" "$ROOT/config.json" < "$f" > "$ROOT/a.out" 2> "$ROOT/a.err"; as=$?
  "$ROOT/candidate.bin" "$ROOT/config.json" < "$f" > "$ROOT/c.out" 2> "$ROOT/c.err"; cs=$?
  set -e
  if [ "$as" -ne "$cs" ] || ! cmp -s "$ROOT/a.out" "$ROOT/c.out"; then
    printf 'SEMANTIC_MISMATCH\t%s\tablated=%s\tcandidate=%s\n' "$f" "$as" "$cs" | tee -a "$ROOT/evidence/semantic-mismatches.tsv"
  else
    printf 'MATCH\t%s\t%s\n' "$cs" "$f" >> "$ROOT/evidence/correctness.tsv"
  fi
done < "$ROOT/evidence/built-exports.txt"

exports=$(wc -l < "$ROOT/evidence/built-exports.txt")
mismatches=$(grep -c '^SEMANTIC_MISMATCH' "$ROOT/evidence/semantic-mismatches.tsv" || true)
{
  printf 'source_sha=%s\n' "$SOURCE_SHA"
  printf 'arena_sha=%s\n' "$ARENA_SHA"
  printf 'exports=%s\n' "$exports"
  printf 'semantic_mismatches=%s\n' "$mismatches"
} | tee "$ROOT/evidence/summary.txt"
test "$mismatches" -eq 0
echo 'QCKN_R2_UNFOLD_NEUTRAL_FULL_SEMANTIC_PARITY_PASS' | tee -a "$ROOT/evidence/summary.txt"
