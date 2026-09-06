#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ROOT=/tmp/v73
rm -rf "$ROOT" && mkdir -p "$ROOT"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
cp -a "$ROOT/base" "$ROOT/repair"

# JOIN(v61 Pi success, v66/v67 env failures, v72 env-projection negative):
# producer-side state compression is not the profitable boundary.  Move the
# interface to the consumer's demanded consequence.  Here the target is WHNF:
# several source variants already CERTIFY WHNF and should not enter generic
# store_lookup/force machinery.  Pi was already retained; this test asks
# whether the same directed Source -> TargetKind rule extends to Lam/Sort/lits.
python3 - "$ROOT/repair" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/eval.rs'
s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {
        if matches!(v, Value::Pi { .. }) { return v; }
        if let Some(r) = self.store_lookup(depth, v) {
"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {
        if matches!(v,
            Value::Pi { .. }
            | Value::Lam { .. }
            | Value::Sort { .. }
            | Value::NatLit { .. }
            | Value::StrLit { .. }
        ) { return v; }
        if let Some(r) = self.store_lookup(depth, v) {
"""
assert s.count(old)==1, 'force_all entry not found exactly once'
p.write_text(s.replace(old,new,1))
PY

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
echo V73_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)
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
  echo "V73_${corpus^^}_REPLAY=EXACT"
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
rows=list(csv.DictReader(open('/tmp/v73/timings.csv')))
deltas=[]
print('HYPOTHESIS=MSI_CONSUMER_DEMAND_SOURCE_TO_TARGETKIND')
print('REPAIR=STABLE_WHNF_CERTIFICATE_FAST_PATH')
print('JOIN_INPUTS=PI_SUCCESS+ENV_CACHE_NEGATIVES+V72_NEGATIVE')
for corpus in ('std','cedar','mathlib'):
    med={arm:statistics.median(float(r['seconds']) for r in rows if r['corpus']==corpus and r['arm']==arm)
         for arm in ('base','repair')}
    d=(med['repair']/med['base']-1)*100
    deltas.append(d)
    print(f'V73_{corpus.upper()}_BASE_MEDIAN={med["base"]:.3f}')
    print(f'V73_{corpus.upper()}_REPAIR_MEDIAN={med["repair"]:.3f}')
    print(f'V73_{corpus.upper()}_DELTA_PCT={d:.4f}')
geo=(math.prod(1+d/100 for d in deltas)**(1/len(deltas))-1)*100
print(f'V73_GEOMEAN_DELTA_PCT={geo:.4f}')
if geo <= -4.0 and max(deltas) <= 0:
    print('DECISION=BIG_SIGNAL__PROMOTE_TO_PGO_ARENA_GATE')
elif geo <= -1.0 and max(deltas) <= 0.5:
    print('DECISION=POSITIVE__CONSUMER_DEMAND_REPRESENTATION_HAS_TEETH__REFINE')
else:
    print('DECISION=NO_MATERIAL_SIGNAL__NEXT_RESIDUAL_IS_CALLER_SPECIFIC_TARGET_KIND')
PY
