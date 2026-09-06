#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ROOT=/tmp/v74
rm -rf "$ROOT" && mkdir -p "$ROOT"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
cp -a "$ROOT/base" "$ROOT/repair"

# v73 residual: Source->TargetKind was still too coarse because the same
# stable-WHNF shortcut helped Std/Cedar but hurt Mathlib. Refine exactly one
# quotient axis: CallerCtx.  This arm specializes only the spine type consumer,
# where the continuation asks specifically for a Pi.  Stable non-Pi WHNF can be
# returned without generic store_lookup/force work; reducible sources still use
# the ordinary force_all path.
python3 - "$ROOT/repair" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/eval.rs'
s=p.read_text()
anchor="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {
        if matches!(v, Value::Pi { .. }) { return v; }
"""
helper="""    #[inline]\n    fn force_pi_for_spine(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        match v {\n            Value::Pi { .. }\n            | Value::Lam { .. }\n            | Value::Sort { .. }\n            | Value::NatLit { .. }\n            | Value::StrLit { .. } => v,\n            _ => self.force_all(depth, v),\n        }\n    }\n\n""" + anchor
assert s.count(anchor)==1, 'force_all anchor not found exactly once'
s=s.replace(anchor, helper, 1)
old="let ty_f = self.force_all(depth, ty);"
assert s.count(old)==1, f'expected one spine Pi-demand call, found {s.count(old)}'
s=s.replace(old, "let ty_f = self.force_pi_for_spine(depth, ty);", 1)
p.write_text(s)
PY

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
echo V74_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done

build(){ arm=$1; cd "$ROOT/$arm"; RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q; cp target/release/sokonanoda "$ROOT/$arm.bin"; }
build base
build repair
mkdir -p "$ROOT/out"
echo 'corpus,arm,pass,seconds' > "$ROOT/timings.csv"

for corpus in std cedar mathlib; do
  "$ROOT/base.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/base-$corpus.out"
  "$ROOT/repair.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/repair-$corpus.out"
  cmp "$ROOT/out/base-$corpus.out" "$ROOT/out/repair-$corpus.out"
  echo "V74_${corpus^^}_REPLAY=EXACT"
  for pass in 1 2 3; do
    if (( pass % 2 == 1 )); then order='base repair'; else order='repair base'; fi
    for arm in $order; do
      sec=$(/usr/bin/time -f '%e' -o "$ROOT/t" "$ROOT/$arm.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" >/dev/null; cat "$ROOT/t")
      echo "$corpus,$arm,$pass,$sec" >> "$ROOT/timings.csv"
    done
  done
done

python3 - <<'PY' | tee "$ROOT/summary.txt"
import csv,statistics,math
rows=list(csv.DictReader(open('/tmp/v74/timings.csv')))
deltas=[]
print('HYPOTHESIS=MSI_CALLERCTX_SOURCE_TARGETKIND_REFINEMENT')
print('REPAIR=SPINE_TYPE_PI_DEMAND_SPECIALIZATION')
print('RESIDUAL_FROM=V73_GENERIC_TARGETKIND_MATHLIB_REGRESSION')
for corpus in ('std','cedar','mathlib'):
    med={arm:statistics.median(float(r['seconds']) for r in rows if r['corpus']==corpus and r['arm']==arm)
         for arm in ('base','repair')}
    d=(med['repair']/med['base']-1)*100
    deltas.append(d)
    print(f'V74_{corpus.upper()}_BASE_MEDIAN={med["base"]:.3f}')
    print(f'V74_{corpus.upper()}_REPAIR_MEDIAN={med["repair"]:.3f}')
    print(f'V74_{corpus.upper()}_DELTA_PCT={d:.4f}')
geo=(math.prod(1+d/100 for d in deltas)**(1/len(deltas))-1)*100
print(f'V74_GEOMEAN_DELTA_PCT={geo:.4f}')
if geo <= -4.0 and max(deltas) <= 0:
    print('DECISION=BIG_SIGNAL__CALLERCTX_REFINEMENT_WORKS__PROMOTE')
elif geo <= -1.0 and max(deltas) <= 0.5:
    print('DECISION=POSITIVE__CALLERCTX_IS_CONSEQUENTIAL__EXPAND_TO_NEXT_PI_CALLER')
elif deltas[2] < 0:
    print('DECISION=MATHLIB_DIRECTION_FLIPPED_POSITIVE__CALLERCTX_FORCED__REFINE_AND_COMPOUND')
else:
    print('DECISION=NO_SIGNAL__SPINE_CALLER_NOT_THE_MISSING_CONTEXT__SPLIT_NEXT_CALLER_FAMILY')
PY
