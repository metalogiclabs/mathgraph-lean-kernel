#!/usr/bin/env bash
set -euo pipefail
OLD=792a5f99bcee9ca3181a01b68be9e5ce2ab6d8d6
NEW=28c03d0103e004610e4d47a4828965efb2b70af9
ARENA=ac1c13762de41b594fa24b90ede8cfd97ac6a765
ROOT=/tmp/upstream-delta-v115
rm -rf "$ROOT"
mkdir -p "$ROOT/out"

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/old"
git -C "$ROOT/old" checkout -q "$OLD"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/new"
git -C "$ROOT/new" checkout -q "$NEW"
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude >/dev/null
nix develop -c ./lka.py build-test mathlib >/dev/null

build_pgo() {
  local dir="$1"; local tag="$2"
  cd "$dir"
  rm -rf pgo
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$dir/pgo" cargo build --release --locked -q
  target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
  cd "$ROOT/arena"
  nix develop -c llvm-profdata merge -o "$dir/pgo/merged.profdata" "$dir/pgo"
  cd "$dir"
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=$dir/pgo/merged.profdata" cargo build --release --locked -q
  echo "V115_PGO_$tag=PASS"
}
build_pgo "$ROOT/old" OLD
build_pgo "$ROOT/new" NEW

for tag in OLD NEW; do
  dir="$ROOT/$(printf '%s' "$tag" | tr '[:upper:]' '[:lower:]')"
  out="$ROOT/out/$tag"
  echo "V115_BEGIN tag=$tag test=mathlib"
  /usr/bin/time -f 'wall=%e rss_kb=%M user=%U sys=%S' -o "$out.time" \
    "$dir/target/release/sokonanoda" "$ROOT/config.json" \
    < "$ROOT/arena/_build/tests/mathlib.ndjson" >"$out.stdout" 2>"$out.stderr"
  echo "V115_RESULT tag=$tag test=mathlib $(cat "$out.time")"
done

echo "V115_COMPLETE=PASS"
