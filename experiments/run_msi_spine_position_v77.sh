#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ROOT=/tmp/v77
rm -rf "$ROOT" && mkdir -p "$ROOT"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"

# v76 residual: N=(NatLit|StrLit) gives ~6% on Cedar/Mathlib but regresses Std;
# O=Sort is broad-positive and especially strong on Mathlib. Refine the winning
# spine caller by APPLICATION POSITION. Four binary axes:
# bit0 NF = N on first application in spine
# bit1 NL = N on later applications
# bit2 OF = O on first application
# bit3 OL = O on later applications
# Exhaust the complete 4-axis version space (15 nonempty repairs).
ARMS=()
for m in $(seq 1 15); do ARMS+=("m$(printf '%02d' "$m")"); done
for arm in "${ARMS[@]}"; do cp -a "$ROOT/base" "$ROOT/$arm"; done

python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
for mask in range(1,16):
    arm=f'm{mask:02d}'
    p=root/arm/'src/eval.rs'
    s=p.read_text()
    fn_anchor="""    fn spine_type_with_value(&mut self, depth: u32, mut ty: V<'t>, prev_head: V<'t>, spine: S<'t>) -> V<'t> {\n        let mut prev = prev_head;\n        for elim in spine.to_vec() {\n"""
    assert s.count(fn_anchor)==1, (arm, s.count(fn_anchor))
    helper=f"""    #[inline]\n    fn force_pi_for_spine_v77(&mut self, depth: u32, v: V<'t>, app_pos: usize) -> V<'t> {{\n        let first = app_pos == 0;\n        match v {{\n            Value::Pi {{ .. }} => v,\n            Value::NatLit {{ .. }} | Value::StrLit {{ .. }}\n                if (first && ({mask}u8 & 1) != 0) || (!first && ({mask}u8 & 2) != 0) => v,\n            Value::Sort {{ .. }}\n                if (first && ({mask}u8 & 4) != 0) || (!first && ({mask}u8 & 8) != 0) => v,\n            _ => self.force_all(depth, v),\n        }}\n    }}\n\n"""
    repl=helper+"""    fn spine_type_with_value(&mut self, depth: u32, mut ty: V<'t>, prev_head: V<'t>, spine: S<'t>) -> V<'t> {\n        let mut prev = prev_head;\n        let mut app_pos = 0usize;\n        for elim in spine.to_vec() {\n"""
    s=s.replace(fn_anchor,repl,1)
    old='''                ElimView::App(a) => {\n                    let ty_f = self.force_all(depth, ty);\n'''
    new='''                ElimView::App(a) => {\n                    let ty_f = self.force_pi_for_spine_v77(depth, ty, app_pos);\n                    app_pos += 1;\n'''
    assert s.count(old)==1, (arm,s.count(old))
    s=s.replace(old,new,1)
    p.write_text(s)
PY

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
echo V77_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done

build(){ arm=$1; cd "$ROOT/$arm"; RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q; cp target/release/sokonanoda "$ROOT/$arm.bin"; }
build base
for a in "${ARMS[@]}"; do build "$a"; done
mkdir -p "$ROOT/out"
echo 'corpus,arm,pass,seconds' > "$ROOT/timings.csv"

# First require exact output replay for every arm/corpus.
for corpus in std cedar mathlib; do
  "$ROOT/base.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/base-$corpus.out"
  for a in "${ARMS[@]}"; do
    "$ROOT/$a.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/$a-$corpus.out"
    cmp "$ROOT/out/base-$corpus.out" "$ROOT/out/$a-$corpus.out"
  done
  echo "V77_${corpus^^}_ALL_ARMS_REPLAY=EXACT"
done

# Balanced 3-pass timing. Reverse the order on pass 2 to reduce drift bias.
for corpus in std cedar mathlib; do
  forward="base ${ARMS[*]}"
  reverse=""
  for ((i=${#ARMS[@]}-1;i>=0;i--)); do reverse+=" ${ARMS[$i]}"; done
  reverse+=" base"
  for pass in 1 2 3; do
    if (( pass % 2 == 1 )); then order="$forward"; else order="$reverse"; fi
    for arm in $order; do
      sec=$(/usr/bin/time -f '%e' -o "$ROOT/t" "$ROOT/$arm.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" >/dev/null; cat "$ROOT/t")
      echo "$corpus,$arm,$pass,$sec" >> "$ROOT/timings.csv"
    done
  done
done

python3 - <<'PY' | tee "$ROOT/summary.txt"
import csv,statistics,math
rows=list(csv.DictReader(open('/tmp/v77/timings.csv')))
corpora=['std','cedar','mathlib']
base={c:statistics.median(float(r['seconds']) for r in rows if r['corpus']==c and r['arm']=='base') for c in corpora}
print('HYPOTHESIS=MSI_SPINE_SOURCE_SHAPE_X_APPLICATION_POSITION')
print('AXES=bit0_N_FIRST,bit1_N_LATER,bit2_SORT_FIRST,bit3_SORT_LATER')
best=None
for mask in range(1,16):
    a=f'm{mask:02d}'
    labels=[]
    if mask&1: labels.append('NF')
    if mask&2: labels.append('NL')
    if mask&4: labels.append('OF')
    if mask&8: labels.append('OL')
    print(f'V77_{a}_LABEL={"+".join(labels)}')
    ds=[]
    for c in corpora:
        med=statistics.median(float(r['seconds']) for r in rows if r['corpus']==c and r['arm']==a)
        d=(med/base[c]-1)*100; ds.append(d)
        print(f'V77_{a}_{c.upper()}_DELTA_PCT={d:.4f}')
    geo=(math.prod(1+d/100 for d in ds)**(1/3)-1)*100
    print(f'V77_{a}_GEOMEAN_DELTA_PCT={geo:.4f}')
    key=(geo,max(ds),mask)
    if best is None or key<best[0]: best=(key,ds)
(geo,mx,mask),ds=best
labels=[]
if mask&1: labels.append('NF')
if mask&2: labels.append('NL')
if mask&4: labels.append('OF')
if mask&8: labels.append('OL')
print(f'V77_WINNER=m{mask:02d}')
print(f'V77_WINNER_LABEL={"+".join(labels)}')
print(f'V77_WINNER_GEOMEAN_DELTA_PCT={geo:.4f}')
print(f'V77_WINNER_MAX_CORPUS_DELTA_PCT={mx:.4f}')
if geo <= -5.0 and mx <= 0:
    print('DECISION=CLEAR_MARGIN__PROMOTE_IMMEDIATE_FRESH_PGO_ARENA_GATE')
elif geo <= -4.0 and mx <= 0.25:
    print('DECISION=NUMBER_ONE_CANDIDATE__PROMOTE_FRESH_PGO_ARENA_GATE')
elif geo <= -2.5 and mx <= 0.5:
    print('DECISION=STRONG_POSITIVE__POSITION_SEPARATOR_FOUND__REFINE_WINNER_NEXT')
elif geo <= -1.0 and mx <= 0.5:
    print('DECISION=POSITIVE__POSITION_IS_CONSEQUENTIAL__RETAIN_MINIMALLY')
else:
    print('DECISION=POSITION_NOT_SUFFICIENT__CHANGE_TO_PREVIOUS_ELIM_OR_SPINE_LENGTH_RELATION')
PY
