#!/usr/bin/env bash
set -euo pipefail

ARENA_SHA=510fbfead6f02bed1a0179d01729a6ddf5bfd06d
ROOT=/tmp/qckn-var-r2-unfold-neutral-v1
ARENA_REPO=https://github.com/leanprover/lean-kernel-arena
CANDIDATE_SHA="${GITHUB_SHA:?GITHUB_SHA required}"

rm -rf "$ROOT"
mkdir -p "$ROOT/evidence"

git worktree add "$ROOT/candidate" "$CANDIDATE_SHA"
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

git clone -q "$ARENA_REPO" "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA_SHA"
cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

cat >"$ROOT/evidence/provenance.tsv" <<EOF
candidate_sha	$CANDIDATE_SHA
active_base_sha	74dc5ddb4584e1254f5687615e5b02795b8dc6f3
arena_sha	$ARENA_SHA
intervention	ordinary_unfold_direct_neutral_app
ablation	EVAL_PLAIN_UNFOLD_NEUTRAL_FAST=false
observed_source_count	174167102
observed_source_share_simple_apply	0.611965
EOF

cd "$ROOT/arena"
nix develop -c ./lka.py build-test mathlib

for arm in ablated candidate; do
  (
    cd "$ROOT/$arm"
    RUSTFLAGS='-C target-cpu=native' cargo build --release --locked
    cp target/release/sokonanoda "$ROOT/$arm.bin"
  )
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
for arm in rows: assert len(rows[arm])==3
aw=median(x[0] for x in rows["ablated"]); cw=median(x[0] for x in rows["candidate"])
au=median(x[1] for x in rows["ablated"]); cu=median(x[1] for x in rows["candidate"])
ar=median(x[2] for x in rows["ablated"]); cr=median(x[2] for x in rows["candidate"])
ws=aw/cw; us=au/cu
print(f"ablated_wall_med_s={aw:.6f}")
print(f"candidate_wall_med_s={cw:.6f}")
print(f"wall_speedup={ws:.6f}")
print(f"ablated_user_med_s={au:.6f}")
print(f"candidate_user_med_s={cu:.6f}")
print(f"user_speedup={us:.6f}")
print(f"ablated_rss_med_kb={int(ar)}")
print(f"candidate_rss_med_kb={int(cr)}")
assert ws >= 1.003 or us >= 1.003, (
    f"RESERVE: ordinary-unfold neutral fast path below 0.3% native threshold "
    f"(wall={ws:.6f} user={us:.6f})"
)
print("QCKN_R2_UNFOLD_NEUTRAL_NATIVE_MATHLIB_PASS")
print("NEXT=CALLGRIND_AND_FULL_SEMANTIC_QUALIFICATION")
PY
