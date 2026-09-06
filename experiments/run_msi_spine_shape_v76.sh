#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ROOT=/tmp/v76
rm -rf "$ROOT" && mkdir -p "$ROOT"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"

# v75 residual: caller=S is consequential, but adding other Pi-demand callers dilutes gain.
# Refine inside S by SourceShape. Axes are the stable non-Pi forms that v74 bypassed:
# L=Lam, O=Sort, N=NatLit|StrLit. Pi is already fast in BASE force_all.
ARMS=(L O N LO LN ON LON)
for arm in "${ARMS[@]}"; do cp -a "$ROOT/base" "$ROOT/$arm"; done

python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
for arm in ['L','O','N','LO','LN','ON','LON']:
    p=root/arm/'src/eval.rs'
    s=p.read_text()
    anchor="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n"""
    pats=['Value::Pi { .. }']
    if 'L' in arm: pats.append('Value::Lam { .. }')
    if 'O' in arm: pats.append('Value::Sort { .. }')
    if 'N' in arm: pats += ['Value::NatLit { .. }','Value::StrLit { .. }']
    match='\n            | '.join(pats)
    helper=f"""    #[inline]\n    fn force_pi_for_spine_v76(&mut self, depth: u32, v: V<'t>) -> V<'t> {{\n        match v {{\n            {match} => v,\n            _ => self.force_all(depth, v),\n        }}\n    }}\n\n""" + anchor
    assert s.count(anchor)==1
    s=s.replace(anchor,helper,1)
    old='let ty_f = self.force_all(depth, ty);'
    assert s.count(old)==1, (arm,s.count(old))
    s=s.replace(old,'let ty_f = self.force_pi_for_spine_v76(depth, ty);',1)
    p.write_text(s)
PY

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
echo V76_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done

build(){ arm=$1; cd "$ROOT/$arm"; RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q; cp target/release/sokonanoda "$ROOT/$arm.bin"; }
build base
for a in "${ARMS[@]}"; do build "$a"; done
mkdir -p "$ROOT/out"
echo 'corpus,arm,pass,seconds' > "$ROOT/timings.csv"

for corpus in std cedar mathlib; do
  "$ROOT/base.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/base-$corpus.out"
  for a in "${ARMS[@]}"; do
    "$ROOT/$a.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/$a-$corpus.out"
    cmp "$ROOT/out/base-$corpus.out" "$ROOT/out/$a-$corpus.out"
  done
  echo "V76_${corpus^^}_ALL_ARMS_REPLAY=EXACT"
  for pass in 1 2 3; do
    if (( pass % 2 == 1 )); then order='base L O N LO LN ON LON'; else order='LON ON LN LO N O L base'; fi
    for arm in $order; do
      sec=$(/usr/bin/time -f '%e' -o "$ROOT/t" "$ROOT/$arm.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" >/dev/null; cat "$ROOT/t")
      echo "$corpus,$arm,$pass,$sec" >> "$ROOT/timings.csv"
    done
  done
done

python3 - <<'PY' | tee "$ROOT/summary.txt"
import csv,statistics,math
rows=list(csv.DictReader(open('/tmp/v76/timings.csv')))
arms=['L','O','N','LO','LN','ON','LON']
corpora=['std','cedar','mathlib']
base={c:statistics.median(float(r['seconds']) for r in rows if r['corpus']==c and r['arm']=='base') for c in corpora}
print('HYPOTHESIS=MSI_SPINE_CALLER_SOURCE_SHAPE_REFINEMENT')
print('AXES=L_LAM,O_SORT,N_NATLIT_STRLIT')
best=None
for a in arms:
    ds=[]
    for c in corpora:
        med=statistics.median(float(r['seconds']) for r in rows if r['corpus']==c and r['arm']==a)
        d=(med/base[c]-1)*100; ds.append(d)
        print(f'V76_{a}_{c.upper()}_DELTA_PCT={d:.4f}')
    geo=(math.prod(1+d/100 for d in ds)**(1/3)-1)*100
    print(f'V76_{a}_GEOMEAN_DELTA_PCT={geo:.4f}')
    key=(geo,max(ds),a)
    if best is None or key<best[0]: best=(key,ds)
(_,mx,w),ds=best
print(f'V76_WINNER={w}')
print(f'V76_WINNER_GEOMEAN_DELTA_PCT={best[0][0]:.4f}')
print(f'V76_WINNER_MAX_CORPUS_DELTA_PCT={mx:.4f}')
if best[0][0] <= -4.0 and mx <= 0:
    print('DECISION=BIG_SIGNAL__SOURCE_SHAPE_ISOLATED__PROMOTE_PGO_GATE')
elif best[0][0] <= -2.0 and mx <= 0.5:
    print('DECISION=STRONG_POSITIVE__REFINE_WINNING_SHAPE_BY_SPINE_POSITION')
elif best[0][0] <= -1.0 and mx <= 0.5:
    print('DECISION=POSITIVE__SOURCE_SHAPE_CONSEQUENTIAL__REFINE_NEXT_AXIS')
else:
    print('DECISION=NO_STABLE_SHAPE_SEPARATOR__CHANGE_TO_SPINE_SHAPE_AXIS')
PY
# v76 trigger
