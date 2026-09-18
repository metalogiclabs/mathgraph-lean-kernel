#!/usr/bin/env bash
set -euo pipefail

ARENA_SHA=510fbfead6f02bed1a0179d01729a6ddf5bfd06d
ROOT=/tmp/qckn-eval-var-fast-v1
ARENA_REPO=https://github.com/leanprover/lean-kernel-arena
CANDIDATE_SHA="${GITHUB_SHA:?GITHUB_SHA required}"

rm -rf "$ROOT"
mkdir -p "$ROOT/evidence"

git worktree add "$ROOT/candidate" "$CANDIDATE_SHA"
cp -a "$ROOT/candidate" "$ROOT/ablated"
python3 - "$ROOT/ablated/src/eval.rs" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
old='pub(crate) const EVAL_DIRECT_VAR_FAST: bool = true;'
new='pub(crate) const EVAL_DIRECT_VAR_FAST: bool = false;'
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY

git clone -q "$ARENA_REPO" "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA_SHA"

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cat >"$ROOT/evidence/provenance.tsv" <<EOF
candidate_sha	$CANDIDATE_SHA
leader_sha	28c03d0103e004610e4d47a4828965efb2b70af9
arena_sha	$ARENA_SHA
intervention	direct_var_eval_dispatch
ablation	EVAL_DIRECT_VAR_FAST=false
promotion_target	mathlib
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test mathlib

for arm in ablated candidate; do
  (
    cd "$ROOT/$arm"
    RUSTFLAGS='-C target-cpu=native' cargo build --release --locked
    cp target/release/sokonanoda "$ROOT/$arm.bin"
  )
  sha256sum "$ROOT/$arm.bin" >> "$ROOT/evidence/binaries.sha256"
done

: > "$ROOT/evidence/mathlib-native.tsv"
for rep in 1 2 3; do
  for arm in ablated candidate; do
    set +e
    /usr/bin/time -f '%e\t%U\t%S\t%M' -o "$ROOT/t" \
      "$ROOT/$arm.bin" "$ROOT/config.json" \
      < "$ROOT/arena/_build/tests/mathlib.ndjson" >/dev/null 2>/dev/null
    st=$?
    set -e
    read -r wall user sys rss < "$ROOT/t"
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$arm" "$rep" "$st" "$wall" "$user" "$rss" | tee -a "$ROOT/evidence/mathlib-native.tsv"
  done
done

python3 - "$ROOT/evidence/mathlib-native.tsv" <<'PY' | tee "$ROOT/evidence/scorecard.txt"
from statistics import median
import sys
rows={"ablated":[],"candidate":[]}
for line in open(sys.argv[1]):
    arm,rep,status,wall,user,rss=line.rstrip().split("\t")
    assert int(status)==0, (arm,rep,status)
    rows[arm].append((float(wall),float(user),int(rss)))
for arm in rows:
    assert len(rows[arm])==3
aw=median(x[0] for x in rows["ablated"])
cw=median(x[0] for x in rows["candidate"])
au=median(x[1] for x in rows["ablated"])
cu=median(x[1] for x in rows["candidate"])
ar=median(x[2] for x in rows["ablated"])
cr=median(x[2] for x in rows["candidate"])
wall_speed=aw/cw
user_speed=au/cu
print(f"ablated_wall_med_s={aw:.6f}")
print(f"candidate_wall_med_s={cw:.6f}")
print(f"wall_speedup={wall_speed:.6f}")
print(f"ablated_user_med_s={au:.6f}")
print(f"candidate_user_med_s={cu:.6f}")
print(f"user_speedup={user_speed:.6f}")
print(f"ablated_rss_med_kb={int(ar)}")
print(f"candidate_rss_med_kb={int(cr)}")
# Native wall is only a cheap promotion gate; require a visible signal before expensive Callgrind.
assert wall_speed >= 1.003 or user_speed >= 1.003, (
    f"RESERVE: direct Var fast path did not improve native Mathlib by >=0.3% "
    f"(wall={wall_speed:.6f} user={user_speed:.6f})"
)
print("QCKN_DIRECT_VAR_NATIVE_MATHLIB_PASS")
print("NEXT=CALLGRIND_AND_FULL_SEMANTIC_QUALIFICATION")
PY
