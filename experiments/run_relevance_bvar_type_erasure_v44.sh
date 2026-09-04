#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v44-base /tmp/v44-cand /tmp/v44-arena

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v44-arena
(cd /tmp/v44-arena && for t in std cedar; do nix develop -c ./lka.py build-test "$t"; done)

git worktree add /tmp/v44-base "$BASE"
git worktree add /tmp/v44-cand "$BASE"

# Pi-only verified incumbent in both arms.
for d in /tmp/v44-base /tmp/v44-cand; do
python3 - "$d" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/eval.rs'; s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY
done

# v44 candidate: relevance-only BVars are keyed by binder level, erasing type identity
# from the temporary analysis witness. The BVar still stores the first observed type;
# exact replay decides whether later relevance computation ever observes that type.
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v44-cand/src/relevance.rs'); s=p.read_text()
s=s.replace('use crate::value::{Spine, Value, S};','use crate::value::{self, Spine, Value, S};')
old='''            let fresh = self.mk_bvar_hc(depth, d);\n            cur = self.apply_closure(depth + 1, body, fresh, Some(d));'''
new='''            let key = (depth, 0usize);\n            let fresh = if let Some(v) = self.tc_cache.bvar_hc.get(&key) {\n                v\n            } else {\n                let empty = self.empty_spine();\n                let v = value::mk_bvar_with_empty(self.arena, depth, d, empty);\n                self.tc_cache.bvar_hc.insert(key, v);\n                v\n            };\n            cur = self.apply_closure(depth + 1, body, fresh, Some(d));'''
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY

cat >/tmp/v44-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

for d in /tmp/v44-base /tmp/v44-cand; do
  (cd "$d" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
done
cp /tmp/v44-base/target/release/sokonanoda /tmp/v44-base-bin
cp /tmp/v44-cand/target/release/sokonanoda /tmp/v44-cand-bin

for t in std cedar; do
  /tmp/v44-base-bin /tmp/v44-config.json < "/tmp/v44-arena/_build/tests/$t.ndjson" >"/tmp/v44-$t-base.out" 2>"/tmp/v44-$t-base.err"
  /tmp/v44-cand-bin /tmp/v44-config.json < "/tmp/v44-arena/_build/tests/$t.ndjson" >"/tmp/v44-$t-cand.out" 2>"/tmp/v44-$t-cand.err"
  cmp "/tmp/v44-$t-base.out" "/tmp/v44-$t-cand.out"
  echo "V44_${t^^}_SEMANTIC_REPLAY=EXACT"
  for arm in base cand cand base; do
    n=$(find /tmp -maxdepth 1 -type f -name "v44-${t}-${arm}-*.time" | wc -l); n=$((n+1))
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v44-${t}-${arm}-${n}.time" "/tmp/v44-$arm-bin" /tmp/v44-config.json < "/tmp/v44-arena/_build/tests/$t.ndjson" >/dev/null 2>"/tmp/v44-${t}-${arm}-${n}.err"
  done
done

python3 - <<'PY' | tee /tmp/v44-decision.txt
from pathlib import Path
import statistics

def med(t,a):
    xs=[]
    for p in Path('/tmp').glob(f'v44-{t}-{a}-*.time'):
        e,u,s,r=p.read_text().split(); xs.append((float(e),float(u)+float(s),int(r)))
    return statistics.median(x[0] for x in xs), statistics.median(x[1] for x in xs)
score=[]
for t in ('std','cedar'):
    bw,bc=med(t,'base'); cw,cc=med(t,'cand'); d=(cw-bw)/bw*100
    score.append(cw/bw)
    print(f'V44_{t.upper()}_BASE_WALL={bw:.3f} CAND_WALL={cw:.3f} DELTA={d:+.3f}%')
    print(f'V44_{t.upper()}_BASE_CPU={bc:.3f} CAND_CPU={cc:.3f}')
mean=(sum(score)/len(score)-1)*100
print(f'V44_MEAN_NORMALIZED_DELTA={mean:+.3f}%')
if mean <= -2:
    print('DECISION=V44_TYPE_IDENTITY_NOT_OBSERVED_AND_MATERIAL_GAIN__ADVANCE_MINIMAL_BINDER_WITNESS')
elif mean < 0:
    print('DECISION=V44_TYPE_IDENTITY_NOT_OBSERVED_WEAK_GAIN__TRANSFER_GATE_BEFORE_REDESIGN')
else:
    print('DECISION=V44_EXACT_BUT_NO_GAIN__TYPE_ERASURE_ALONE_DOES_NOT_PAY')
print('RULE=EXACT_REPLAY_REQUIRED__NO_PROMOTION_ON_TIMING_ONLY')
PY
