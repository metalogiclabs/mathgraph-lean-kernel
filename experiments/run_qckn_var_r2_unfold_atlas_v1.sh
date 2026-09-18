#!/usr/bin/env bash
set -euo pipefail

ARENA_SHA=510fbfead6f02bed1a0179d01729a6ddf5bfd06d
ROOT=/tmp/qckn-var-r2-unfold-atlas-v1
ARENA_REPO=https://github.com/leanprover/lean-kernel-arena
SOURCE_SHA="${GITHUB_SHA:?GITHUB_SHA required}"

rm -rf "$ROOT"
mkdir -p "$ROOT/evidence"

cat >"$ROOT/evidence/provenance.tsv" <<EOF
source_sha	$SOURCE_SHA
active_sha	74dc5ddb4584e1254f5687615e5b02795b8dc6f3
arena_sha	$ARENA_SHA
purpose	ordinary_unfold_simple_apply_census
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
RUSTFLAGS='-C target-cpu=native' cargo build --release --locked --features qckn-r2-unfold-atlas
cp target/release/sokonanoda "$ROOT/r2-unfold-atlas.bin"
sha256sum "$ROOT/r2-unfold-atlas.bin" > "$ROOT/evidence/binary.sha256"

set +e
/usr/bin/time -f 'wall_s=%e\nuser_s=%U\nsys_s=%S\nmax_rss_kb=%M' -o "$ROOT/evidence/mathlib.time" \
  "$ROOT/r2-unfold-atlas.bin" "$ROOT/config.json" \
  < "$ROOT/arena/_build/tests/mathlib.ndjson" \
  > "$ROOT/evidence/mathlib.stdout" 2> "$ROOT/evidence/mathlib.stderr"
rc=$?
set -e
echo "$rc" | tee "$ROOT/evidence/mathlib.rc"
test "$rc" -eq 0

grep '^QCKN_R2_UNFOLD_ATLAS' "$ROOT/evidence/mathlib.stderr" > "$ROOT/evidence/unfold-atlas.tsv"
test -s "$ROOT/evidence/unfold-atlas.tsv"

python3 - "$ROOT/evidence/unfold-atlas.tsv" <<'PY' | tee "$ROOT/evidence/summary.txt"
import sys
rows={}
for line in open(sys.argv[1]):
    tag,idx,label,count=line.rstrip().split("\t")
    assert tag=="QCKN_R2_UNFOLD_ATLAS"
    rows[label]=int(count)

labels=[
"ordinary_unfold_total","f_already_canonical","f_canon_cache_hit","f_canon_cache_miss",
"a_already_canonical","a_thunk","a_canon_cache_hit","a_canon_cache_miss",
"app_hc_hit","app_hc_miss",
"spine_len_0","spine_len_1","spine_len_2_3","spine_len_4_7","spine_len_8_plus"
]
assert set(labels) <= set(rows)
total=rows["ordinary_unfold_total"]

f_parts=rows["f_already_canonical"]+rows["f_canon_cache_hit"]+rows["f_canon_cache_miss"]
a_parts=rows["a_already_canonical"]+rows["a_thunk"]+rows["a_canon_cache_hit"]+rows["a_canon_cache_miss"]
app_parts=rows["app_hc_hit"]+rows["app_hc_miss"]
spine_parts=sum(rows[k] for k in labels[10:])
assert total==f_parts,(total,f_parts)
assert total==a_parts,(total,a_parts)
assert total==app_parts,(total,app_parts)
assert total==spine_parts,(total,spine_parts)

print(f"ordinary_unfold_total={total}")
for label in labels[1:]:
    print(f"{label}\tcount={rows[label]}\tshare={rows[label]/total if total else 0:.6f}")

print(f"f_already_canonical_rate={rows['f_already_canonical']/total if total else 0:.6f}")
print(f"a_already_canonical_rate={rows['a_already_canonical']/total if total else 0:.6f}")
print(f"app_hc_hit_rate={rows['app_hc_hit']/total if total else 0:.6f}")
print(f"app_hc_miss_rate={rows['app_hc_miss']/total if total else 0:.6f}")
print(f"shallow_spine_rate={(rows['spine_len_0']+rows['spine_len_1'])/total if total else 0:.6f}")
print("DECISION=OBSERVATIONAL_ORDINARY_UNFOLD_CENSUS_ONLY__NO_INTERVENTION_PROMOTED")
PY
