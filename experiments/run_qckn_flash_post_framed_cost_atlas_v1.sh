#!/usr/bin/env bash
set -euo pipefail

ARENA_SHA=510fbfead6f02bed1a0179d01729a6ddf5bfd06d
ROOT=/tmp/qckn-flash-post-framed-cost-atlas-v1
ARENA_REPO=https://github.com/leanprover/lean-kernel-arena
CANDIDATE_SHA="${GITHUB_SHA:?GITHUB_SHA required}"

rm -rf "$ROOT"
mkdir -p "$ROOT/evidence" "$ROOT/pgo"

cat >"$ROOT/evidence/provenance.tsv" <<EOF
candidate_sha	$CANDIDATE_SHA
active_capabilities	direct_var_eval,direct_framed_prune
arena_sha	$ARENA_SHA
purpose	post_framed_full_mathlib_cost_atlas
authority	callgrind_Ir_development_proxy
promotion_authority	Arena_mathlib_wall_plus_semantic_authority
EOF

git clone -q "$ARENA_REPO" "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA_SHA"

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude
nix develop -c ./lka.py build-test mathlib

cd "$GITHUB_WORKSPACE"
PROFILE_CPU_FLAGS='-C target-cpu=x86-64 -C target-feature=-avx,-avx2,-avx512f,-fma'

rm -rf target "$ROOT/pgo"
mkdir -p "$ROOT/pgo"

RUSTFLAGS="$PROFILE_CPU_FLAGS -Cprofile-generate=$ROOT/pgo" cargo build --release --locked
target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
nix shell nixpkgs#llvmPackages_21.llvm -c llvm-profdata merge -o "$ROOT/pgo/merged.profdata" "$ROOT/pgo"
test -s "$ROOT/pgo/merged.profdata"
rm -rf target
RUSTFLAGS="$PROFILE_CPU_FLAGS -Cprofile-use=$ROOT/pgo/merged.profdata" cargo build --release --locked
cp target/release/sokonanoda "$ROOT/current-profile.bin"
sha256sum "$ROOT/current-profile.bin" > "$ROOT/evidence/binary.sha256"

VALGRIND=$(nix shell nixpkgs#valgrind -c sh -c 'command -v valgrind')
ANNOTATE=$(nix shell nixpkgs#valgrind -c sh -c 'command -v callgrind_annotate')
"$VALGRIND" --version | tee "$ROOT/evidence/valgrind-version.txt"

set +e
/usr/bin/time -f 'wall_s=%e\nuser_s=%U\nsys_s=%S\nmax_rss_kb=%M' -o "$ROOT/evidence/mathlib.time"   timeout 7200s "$VALGRIND" --tool=callgrind --quiet --collect-jumps=no     --callgrind-out-file="$ROOT/evidence/mathlib.callgrind"     "$ROOT/current-profile.bin" "$ROOT/config.json"     < "$ROOT/arena/_build/tests/mathlib.ndjson"     > "$ROOT/evidence/mathlib.stdout" 2> "$ROOT/evidence/mathlib.stderr"
rc=$?
set -e
echo "$rc" | tee "$ROOT/evidence/mathlib.rc"
test "$rc" -eq 0
test -s "$ROOT/evidence/mathlib.callgrind"

summary=$(awk '/^summary:/ {print $2; exit}' "$ROOT/evidence/mathlib.callgrind")
test -n "$summary"
echo "MATHLIB_CALLGRIND_IR=$summary" | tee "$ROOT/evidence/summary.txt"

"$ANNOTATE" --inclusive=no --threshold=0.05 "$ROOT/evidence/mathlib.callgrind" > "$ROOT/evidence/mathlib.self.txt"
"$ANNOTATE" --inclusive=yes --threshold=0.05 "$ROOT/evidence/mathlib.callgrind" > "$ROOT/evidence/mathlib.inclusive.txt"

{
  echo '=== SELF TOP ==='
  sed -n '1,180p' "$ROOT/evidence/mathlib.self.txt"
  echo '=== INCLUSIVE TOP ==='
  sed -n '1,220p' "$ROOT/evidence/mathlib.inclusive.txt"
  echo 'DECISION=PROFILE_POST_FRAMED_PRESENT__DERIVE_ONE_COST_RESIDUAL_ONLY'
} | tee -a "$ROOT/evidence/summary.txt"
