#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ROOT=/tmp/v72
rm -rf "$ROOT" && mkdir -p "$ROOT"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/ablated"
git -C "$ROOT/ablated" checkout -q "$BASE"
cp -a "$ROOT/ablated" "$ROOT/repair"

# Residual class: expressions whose continuation depends on exactly one local.
# Repair: replace the general environment-prune path with the exact one-slot
# directed transition env -> minimal projected env.  The ablated arm is the
# exact same release with this repair absent.
python3 - "$ROOT/repair" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/eval.rs'
s=p.read_text()
old='''    #[inline]
    pub(crate) fn key_env(&mut self, env: E<'t>, e: ExprPtr<'t>) -> E<'t> {
        let k = e.num_loose_bvars();
        if k == 0 {
            return self.lsub_base(env.lsub());
        }
        if k > 64 {
            return env;
        }
        self.prune_env(env, e.as_ref().fv_mask())
    }'''
new='''    #[inline]
    pub(crate) fn key_env(&mut self, env: E<'t>, e: ExprPtr<'t>) -> E<'t> {
        let k = e.num_loose_bvars();
        if k == 0 {
            return self.lsub_base(env.lsub());
        }
        if k > 64 {
            return env;
        }
        let mask = e.as_ref().fv_mask();
        if mask.count_ones() == 1 {
            let idx = mask.trailing_zeros() as u16;
            if let Some(v) = env.lookup(idx) {
                let lsub = env.lsub();
                let mut slots_hash = lsub.map_or(0, |l| l as *const value::LevelSub<'t> as usize as u64);
                slots_hash = slots_hash
                    .wrapping_mul(0x9E3779B97F4A7C15)
                    .wrapping_add(v as *const Value<'t> as usize as u64);
                let hash = mask.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(slots_hash);
                return self.intern_frame(hash, mask, &[v], lsub);
            }
        }
        self.prune_env(env, mask)
    }'''
assert s.count(old)==1, 'expected release key_env not found exactly once'
p.write_text(s.replace(old,new,1))
PY

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
echo V72_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done

build(){ arm=$1; cd "$ROOT/$arm"; RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q; cp target/release/sokonanoda "$ROOT/$arm.bin"; }
build ablated
build repair
mkdir -p "$ROOT/out"
echo 'corpus,arm,pass,seconds' > "$ROOT/timings.csv"

for corpus in std cedar mathlib; do
  "$ROOT/ablated.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/ablated-$corpus.out"
  "$ROOT/repair.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/repair-$corpus.out"
  cmp "$ROOT/out/ablated-$corpus.out" "$ROOT/out/repair-$corpus.out"
  echo "V72_${corpus^^}_REPLAY=EXACT"
  for pass in 1 2 3; do
    # alternate order across passes to reduce order bias
    if (( pass % 2 == 1 )); then order='ablated repair'; else order='repair ablated'; fi
    for arm in $order; do
      sec=$(/usr/bin/time -f '%e' -o "$ROOT/t" "$ROOT/$arm.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" >/dev/null; cat "$ROOT/t")
      echo "$corpus,$arm,$pass,$sec" >> "$ROOT/timings.csv"
    done
  done
done

python3 - <<'PY' | tee "$ROOT/summary.txt"
import csv,statistics,math
rows=list(csv.DictReader(open('/tmp/v72/timings.csv')))
deltas=[]
print('HYPOTHESIS=MSI_RESIDUAL_TO_REPRESENTATION_REPAIR_CAUSAL_LOOP')
print('REPAIR=SINGLE_DEPENDENCY_DIRECT_ENV_PROJECTION')
print('ABLATION=EXACT_REPAIR_REMOVAL')
for corpus in ('std','cedar','mathlib'):
    med={arm:statistics.median(float(r['seconds']) for r in rows if r['corpus']==corpus and r['arm']==arm)
         for arm in ('ablated','repair')}
    d=(med['repair']/med['ablated']-1)*100
    deltas.append(d)
    print(f'V72_{corpus.upper()}_ABLATED_MEDIAN={med["ablated"]:.3f}')
    print(f'V72_{corpus.upper()}_REPAIR_MEDIAN={med["repair"]:.3f}')
    print(f'V72_{corpus.upper()}_CAUSAL_DELTA_PCT={d:.4f}')
geo=(math.prod(1+d/100 for d in deltas)**(1/len(deltas))-1)*100
print(f'V72_GEOMEAN_CAUSAL_DELTA_PCT={geo:.4f}')
if geo <= -4.0 and max(deltas) <= 0:
    print('DECISION=CAUSAL_BIG_SIGNAL__MSI_GENERATED_REPLACEMENT_WORKS__PROMOTE_TO_ARENA_PGO')
elif geo <= -1.0 and max(deltas) <= 0.5:
    print('DECISION=CAUSAL_POSITIVE__METHOD_HAS_TEETH__REFINE_REPRESENTATION')
else:
    print('DECISION=NO_CAUSAL_MATERIAL_GAIN__THIS_REPAIR_FAILS__USE_RESIDUAL_FOR_NEXT_GENESIS')
PY
