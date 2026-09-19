#!/usr/bin/env bash
set -euo pipefail

ARM="${QCKN_ARM:?QCKN_ARM must be candidate or ablated}"
case "$ARM" in candidate|ablated) ;; *) echo "bad arm $ARM" >&2; exit 2;; esac

ARENA_SHA=510fbfead6f02bed1a0179d01729a6ddf5bfd06d
ROOT="/tmp/qckn-r2-unfold-neutral-callgrind-$ARM"
ARENA_REPO=https://github.com/leanprover/lean-kernel-arena
SOURCE_SHA="${GITHUB_SHA:?GITHUB_SHA required}"

rm -rf "$ROOT"
mkdir -p "$ROOT/evidence" "$ROOT/pgo"

git worktree add "$ROOT/src" "$SOURCE_SHA"
if [ "$ARM" = ablated ]; then
  python3 - "$ROOT/src/src/eval.rs" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
old='pub(crate) const EVAL_PLAIN_UNFOLD_NEUTRAL_FAST: bool = true;'
new='pub(crate) const EVAL_PLAIN_UNFOLD_NEUTRAL_FAST: bool = false;'
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY
fi

git clone -q "$ARENA_REPO" "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA_SHA"

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cat >"$ROOT/evidence/provenance.tsv" <<EOF
arm	$ARM
source_sha	$SOURCE_SHA
active_base_sha	74dc5ddb4584e1254f5687615e5b02795b8dc6f3
arena_sha	$ARENA_SHA
counter	callgrind_Ir_development_proxy
build	valgrind_safe_x86_64_no_avx_PGO
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test init-prelude
nix develop -c ./lka.py build-test mathlib

cd "$ROOT/src"
PROFILE_CPU_FLAGS='-C target-cpu=x86-64 -C target-feature=-avx,-avx2,-avx512f,-fma'
RUSTFLAGS="$PROFILE_CPU_FLAGS -Cprofile-generate=$ROOT/pgo" cargo build --release --locked
target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
nix shell nixpkgs#llvmPackages_21.llvm -c llvm-profdata merge -o "$ROOT/pgo/merged.profdata" "$ROOT/pgo"
test -s "$ROOT/pgo/merged.profdata"
rm -rf target
RUSTFLAGS="$PROFILE_CPU_FLAGS -Cprofile-use=$ROOT/pgo/merged.profdata" cargo build --release --locked
cp target/release/sokonanoda "$ROOT/$ARM.bin"
sha256sum "$ROOT/$ARM.bin" > "$ROOT/evidence/binary.sha256"

VALGRIND=$(nix shell nixpkgs#valgrind -c sh -c 'command -v valgrind')
"$VALGRIND" --version | tee "$ROOT/evidence/valgrind-version.txt"

set +e
/usr/bin/time -f 'wall_s=%e\nuser_s=%U\nsys_s=%S\nmax_rss_kb=%M' -o "$ROOT/evidence/mathlib.time" \
  timeout 7200s "$VALGRIND" --tool=callgrind --quiet --collect-jumps=no \
    --callgrind-out-file="$ROOT/evidence/mathlib.callgrind" \
    "$ROOT/$ARM.bin" "$ROOT/config.json" \
    < "$ROOT/arena/_build/tests/mathlib.ndjson" \
    > "$ROOT/evidence/mathlib.stdout" 2> "$ROOT/evidence/mathlib.stderr"
rc=$?
set -e
echo "$rc" | tee "$ROOT/evidence/mathlib.rc"
test "$rc" -eq 0

ir=$(awk '/^summary:/ {print $2; exit}' "$ROOT/evidence/mathlib.callgrind")
test -n "$ir"
printf 'arm=%s\nmathlib_callgrind_ir=%s\n' "$ARM" "$ir" | tee "$ROOT/evidence/summary.txt"
