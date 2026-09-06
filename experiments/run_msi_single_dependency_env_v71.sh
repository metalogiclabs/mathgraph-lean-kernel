#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ROOT=/tmp/v71
rm -rf "$ROOT" && mkdir -p "$ROOT"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
cp -a "$ROOT/base" "$ROOT/msi"
python3 - "$ROOT/msi" <<'PY'
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
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY
cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
git clone -q --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
echo V71_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done
build(){ arm=$1; cd "$ROOT/$arm"; RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q; cp target/release/sokonanoda "$ROOT/$arm.bin"; }
build base
build msi
mkdir -p "$ROOT/out"
echo 'corpus,arm,pass,seconds' > "$ROOT/timings.csv"
for corpus in std cedar mathlib; do
  "$ROOT/base.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/base-$corpus.out"
  "$ROOT/msi.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/msi-$corpus.out"
  cmp "$ROOT/out/base-$corpus.out" "$ROOT/out/msi-$corpus.out"
  echo "V71_${corpus^^}_REPLAY=EXACT"
  for pass in 1 2 3; do
    for arm in base msi; do
      sec=$(/usr/bin/time -f '%e' -o "$ROOT/t" "$ROOT/$arm.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" >/dev/null; cat "$ROOT/t")
      echo "$corpus,$arm,$pass,$sec" >> "$ROOT/timings.csv"
    done
  done
done
python3 - <<'PY' | tee "$ROOT/summary.txt"
import csv,statistics,math
rows=list(csv.DictReader(open('/tmp/v71/timings.csv')))
deltas=[]
for corpus in ('std','cedar','mathlib'):
    vals={}
    for arm in ('base','msi'):
        vals[arm]=statistics.median(float(r['seconds']) for r in rows if r['corpus']==corpus and r['arm']==arm)
    delta=(vals['msi']/vals['base']-1)*100
    deltas.append(delta)
    print(f'V71_{corpus.upper()}_BASE_MEDIAN={vals["base"]:.3f}')
    print(f'V71_{corpus.upper()}_MSI_MEDIAN={vals["msi"]:.3f}')
    print(f'V71_{corpus.upper()}_DELTA_PCT={delta:.4f}')
ratio=math.prod(1+d/100 for d in deltas)**(1/len(deltas))
geo=(ratio-1)*100
print(f'V71_GEOMEAN_DELTA_PCT={geo:.4f}')
if geo <= -4.0 and max(deltas) <= 0:
    print('DECISION=V71_BIG_SIGNAL__PROMOTE_TO_PGO_ARENA_GATE')
elif geo <= -1.0 and max(deltas) <= 0.5:
    print('DECISION=V71_POSITIVE__REFINE_OR_COMBINE')
else:
    print('DECISION=V71_NO_MATERIAL_SIGNAL__KILL')
print('HYPOTHESIS=MSI_SINGLE_DEPENDENCY_ENV_QUOTIENT')
PY
