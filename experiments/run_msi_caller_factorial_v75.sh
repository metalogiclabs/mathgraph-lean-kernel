#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ROOT=/tmp/v75
rm -rf "$ROOT" && mkdir -p "$ROOT"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"

# Three caller-context axes forced by v74. Enumerate every non-empty subset.
# S = spine_type_with_value Pi demand (v74 winner)
# H = const-head type telescope Pi demand
# P = projection type telescope Pi demand
arms=(base S H P SH SP HP SHP)
for arm in S H P SH SP HP SHP; do cp -a "$ROOT/base" "$ROOT/$arm"; done

python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
for arm in ['S','H','P','SH','SP','HP','SHP']:
    p=root/arm/'src/eval.rs'; s=p.read_text()
    anchor="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n"""
    helper="""    #[inline]\n    fn force_pi_ctx(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        match v {\n            Value::Pi { .. } | Value::Lam { .. } | Value::Sort { .. }\n            | Value::NatLit { .. } | Value::StrLit { .. } => v,\n            _ => self.force_all(depth, v),\n        }\n    }\n\n"""+anchor
    assert s.count(anchor)==1
    s=s.replace(anchor,helper,1)
    if 'S' in arm:
        old='let ty_f = self.force_all(depth, ty);'
        assert s.count(old)==1
        s=s.replace(old,'let ty_f = self.force_pi_ctx(depth, ty);',1)
    if 'H' in arm:
        old='let cur_f = self.force_all(binder_depth, cur);'
        n=s.count(old); assert n>=1, n
        s=s.replace(old,'let cur_f = self.force_pi_ctx(binder_depth, cur);')
    if 'P' in arm:
        old='let cf = self.force_all(depth, cur);'
        n=s.count(old); assert n>=1, n
        s=s.replace(old,'let cf = self.force_pi_ctx(depth, cur);')
    p.write_text(s)
PY

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
echo V75_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done

build(){ arm=$1; cd "$ROOT/$arm"; RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q; cp target/release/sokonanoda "$ROOT/$arm.bin"; }
for arm in "${arms[@]}"; do build "$arm"; done
mkdir -p "$ROOT/out"
echo 'corpus,arm,pass,seconds' > "$ROOT/timings.csv"

# Exact replay first: every arm must match base on all three corpora.
for corpus in std cedar mathlib; do
  "$ROOT/base.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/base-$corpus.out"
  for arm in S H P SH SP HP SHP; do
    "$ROOT/$arm.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/$arm-$corpus.out"
    cmp "$ROOT/out/base-$corpus.out" "$ROOT/out/$arm-$corpus.out"
  done
  echo "V75_${corpus^^}_ALL_ARMS_REPLAY=EXACT"
done

# Two balanced passes across all 8 arms: broad factorial screen, then promote winner to PGO gate.
for corpus in std cedar mathlib; do
  for pass in 1 2; do
    if (( pass==1 )); then order='base S H P SH SP HP SHP'; else order='SHP HP SP SH P H S base'; fi
    for arm in $order; do
      sec=$(/usr/bin/time -f '%e' -o "$ROOT/t" "$ROOT/$arm.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" >/dev/null; cat "$ROOT/t")
      echo "$corpus,$arm,$pass,$sec" >> "$ROOT/timings.csv"
    done
  done
done

python3 - <<'PY' | tee "$ROOT/summary.txt"
import csv,statistics,math
rows=list(csv.DictReader(open('/tmp/v75/timings.csv')))
arms=['S','H','P','SH','SP','HP','SHP']
base={c:statistics.median(float(r['seconds']) for r in rows if r['corpus']==c and r['arm']=='base') for c in ('std','cedar','mathlib')}
print('HYPOTHESIS=MSI_CALLERCTX_FACTORIAL_COMPOUNDING')
print('AXES=S_SPINE,H_HEAD_TELESCOPE,P_PROJECTION_TELESCOPE')
best=None
for arm in arms:
    ds=[]
    for c in ('std','cedar','mathlib'):
        m=statistics.median(float(r['seconds']) for r in rows if r['corpus']==c and r['arm']==arm)
        d=(m/base[c]-1)*100; ds.append(d)
        print(f'V75_{arm}_{c.upper()}_DELTA_PCT={d:.4f}')
    geo=(math.prod(1+d/100 for d in ds)**(1/3)-1)*100
    print(f'V75_{arm}_GEOMEAN_DELTA_PCT={geo:.4f}')
    cand=(geo,max(ds),arm,ds)
    if best is None or cand[0] < best[0]: best=cand
geo,mx,arm,ds=best
print(f'V75_WINNER={arm}')
print(f'V75_WINNER_GEOMEAN_DELTA_PCT={geo:.4f}')
print(f'V75_WINNER_MAX_CORPUS_DELTA_PCT={mx:.4f}')
if geo <= -5.0 and mx <= 0:
    print('DECISION=CLEAR_MARGIN_SIGNAL__IMMEDIATE_FRESH_PGO_ARENA_GATE')
elif geo <= -3.0 and mx <= 0.5:
    print('DECISION=STRONG_COMPOUNDING__FRESH_PGO_ARENA_GATE')
elif geo <= -1.0 and mx <= 0.5:
    print('DECISION=POSITIVE__KEEP_WINNER__EXPAND_CALLER_GRAMMAR')
else:
    print('DECISION=NO_COMPOUNDING__RETAIN_V74_S_ONLY_AND_CHANGE_RESIDUAL_CLASS')
PY
