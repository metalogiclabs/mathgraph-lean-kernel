#!/usr/bin/env bash
set -euo pipefail

ARENA_SHA=510fbfead6f02bed1a0179d01729a6ddf5bfd06d
ROOT=/tmp/qckn-var-r2-app-atlas-v1
ARENA_REPO=https://github.com/leanprover/lean-kernel-arena
SOURCE_SHA="${GITHUB_SHA:?GITHUB_SHA required}"

rm -rf "$ROOT"
mkdir -p "$ROOT/evidence"

cat >"$ROOT/evidence/provenance.tsv" <<EOF
source_sha	$SOURCE_SHA
active_sha	74dc5ddb4584e1254f5687615e5b02795b8dc6f3
arena_sha	$ARENA_SHA
purpose	post_var_simple_apply_value_kind_census
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
RUSTFLAGS='-C target-cpu=native' cargo build --release --locked --features qckn-r2-app-atlas
cp target/release/sokonanoda "$ROOT/r2-app-atlas.bin"
sha256sum "$ROOT/r2-app-atlas.bin" > "$ROOT/evidence/binary.sha256"

set +e
/usr/bin/time -f 'wall_s=%e\nuser_s=%U\nsys_s=%S\nmax_rss_kb=%M' -o "$ROOT/evidence/mathlib.time" \
  "$ROOT/r2-app-atlas.bin" "$ROOT/config.json" \
  < "$ROOT/arena/_build/tests/mathlib.ndjson" \
  > "$ROOT/evidence/mathlib.stdout" 2> "$ROOT/evidence/mathlib.stderr"
rc=$?
set -e
echo "$rc" | tee "$ROOT/evidence/mathlib.rc"
test "$rc" -eq 0

grep '^QCKN_R2_APP_ATLAS' "$ROOT/evidence/mathlib.stderr" > "$ROOT/evidence/app-atlas.tsv"
test -s "$ROOT/evidence/app-atlas.tsv"

python3 - "$ROOT/evidence/app-atlas.tsv" <<'PY' | tee "$ROOT/evidence/summary.txt"
import sys
rows={}
for line in open(sys.argv[1]):
    tag,idx,label,count=line.rstrip().split("\t")
    assert tag=="QCKN_R2_APP_ATLAS"
    rows[label]=int(count)

labels=[
"simple_apply_total","rigid_bvar","rigid_axiom","rigid_ctor_nat_succ",
"rigid_ctor_other","rigid_recursor","rigid_quot","rigid_inductive",
"unfold_nat_red","unfold_other","unexpected"
]
assert set(labels) <= set(rows)
total=rows["simple_apply_total"]
parts=sum(rows[k] for k in labels[1:])
print(f"simple_apply_total={total}")
print(f"classified_total={parts}")
assert total == parts, (total,parts)
assert rows["unexpected"] == 0, rows["unexpected"]

print("=== SIMPLE APPLY VALUE KINDS ===")
ranked=[]
for label in labels[1:-1]:
    count=rows[label]
    ranked.append((label,count))
    print(f"{label}\tcount={count}\tshare={count/total if total else 0:.6f}")
ranked.sort(key=lambda kv:kv[1], reverse=True)
print(f"NEXT_KIND={ranked[0][0]}")
print(f"NEXT_KIND_COUNT={ranked[0][1]}")
print(f"NEXT_KIND_SHARE={ranked[0][1]/total if total else 0:.6f}")
print("DECISION=OBSERVATIONAL_SIMPLE_APPLY_KIND_CENSUS_ONLY__NO_INTERVENTION_PROMOTED")
PY
