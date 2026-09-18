#!/usr/bin/env bash
set -euo pipefail

ARENA_SHA=510fbfead6f02bed1a0179d01729a6ddf5bfd06d
ROOT=/tmp/qckn-eval-path-atlas-v1
ARENA_REPO=https://github.com/leanprover/lean-kernel-arena
CANDIDATE_SHA="${GITHUB_SHA:?GITHUB_SHA required}"

rm -rf "$ROOT"
mkdir -p "$ROOT/evidence"

cat >"$ROOT/evidence/provenance.tsv" <<EOF
candidate_sha	$CANDIDATE_SHA
leader_sha	28c03d0103e004610e4d47a4828965efb2b70af9
arena_sha	$ARENA_SHA
purpose	observational_eval_path_census
selector_changed	false
EOF

git clone -q "$ARENA_REPO" "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA_SHA"

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test mathlib

cd "$GITHUB_WORKSPACE"
RUSTFLAGS='-C target-cpu=native' cargo build --release --locked --features qckn-eval-atlas
cp target/release/sokonanoda "$ROOT/eval-atlas.bin"
sha256sum "$ROOT/eval-atlas.bin" > "$ROOT/evidence/binary.sha256"

set +e
/usr/bin/time -f 'wall_s=%e\nuser_s=%U\nsys_s=%S\nmax_rss_kb=%M' -o "$ROOT/evidence/mathlib.time" \
  "$ROOT/eval-atlas.bin" "$ROOT/config.json" \
  < "$ROOT/arena/_build/tests/mathlib.ndjson" \
  > "$ROOT/evidence/mathlib.stdout" 2> "$ROOT/evidence/mathlib.stderr"
rc=$?
set -e
echo "$rc" | tee "$ROOT/evidence/mathlib.rc"
test "$rc" -eq 0

grep '^QCKN_EVAL_ATLAS' "$ROOT/evidence/mathlib.stderr" > "$ROOT/evidence/eval-atlas.tsv"
test -s "$ROOT/evidence/eval-atlas.tsv"

python3 - "$ROOT/evidence/eval-atlas.tsv" <<'PY' | tee "$ROOT/evidence/summary.txt"
import sys
rows={}
for line in open(sys.argv[1]):
    tag,idx,label,count=line.rstrip().split("\t")
    assert tag=="QCKN_EVAL_ATLAS"
    rows[label]=int(count)

required=[
"eval_entry","closed_cache_hit","closed_cache_miss","open_cache_hit","open_cache_miss","direct_no_cache",
"app_chain_same","app_chain_mixed","app_simple_lambda","app_simple_apply",
"var","sort","const","lambda","pi","let","proj","natlit","strlit"
]
assert set(required) <= set(rows)

entry=rows["eval_entry"]
closed=rows["closed_cache_hit"]+rows["closed_cache_miss"]
open_=rows["open_cache_hit"]+rows["open_cache_miss"]
direct=rows["direct_no_cache"]
nocache=rows["closed_cache_miss"]+rows["open_cache_miss"]+direct
paths={k:rows[k] for k in required[6:]}
path_total=sum(paths.values())

print(f"eval_entry={entry}")
print(f"closed_attempts={closed} closed_hit={rows['closed_cache_hit']} closed_miss={rows['closed_cache_miss']} closed_hit_rate={rows['closed_cache_hit']/closed if closed else 0:.6f}")
print(f"open_attempts={open_} open_hit={rows['open_cache_hit']} open_miss={rows['open_cache_miss']} open_hit_rate={rows['open_cache_hit']/open_ if open_ else 0:.6f}")
print(f"direct_no_cache={direct} share_of_eval={direct/entry if entry else 0:.6f}")
print(f"eval_no_cache_calls={nocache} share_of_eval={nocache/entry if entry else 0:.6f}")
print(f"path_total={path_total} expected_nocache={nocache}")
assert path_total == nocache, (path_total,nocache)

print("=== EVAL PATHS ===")
for label,count in sorted(paths.items(), key=lambda kv: kv[1], reverse=True):
    print(f"{label}\tcount={count}\tshare_of_nocache={count/nocache if nocache else 0:.6f}\tshare_of_eval={count/entry if entry else 0:.6f}")

print("=== CACHE COST SURFACE ===")
for label,count in [
    ("closed_cache_lookup",closed),
    ("open_cache_lookup",open_),
    ("direct_no_cache",direct),
]:
    print(f"{label}\tcount={count}\tshare_of_eval={count/entry if entry else 0:.6f}")

print("DECISION=OBSERVATIONAL_EVAL_CENSUS_ONLY__NO_INTERVENTION_PROMOTED")
PY
