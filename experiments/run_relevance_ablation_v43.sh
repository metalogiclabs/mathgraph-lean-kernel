#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v43-base /tmp/v43-abl /tmp/v43-arena

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v43-arena
(cd /tmp/v43-arena && for t in std cedar; do nix develop -c ./lka.py build-test "$t"; done)

git worktree add /tmp/v43-base "$BASE"
git worktree add /tmp/v43-abl "$BASE"

# Pi-only is the current verified wall-time seed; apply to both arms.
for d in /tmp/v43-base /tmp/v43-abl; do
python3 - "$d" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/eval.rs'; s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1; p.write_text(s.replace(old,new,1))
PY
done

# Conservative ablation: never claim an argument/result is ignorable.
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v43-abl/src/relevance.rs'); s=p.read_text()
old="""    pub(crate) fn sig_of(&mut self, name: NamePtr<'t>, levels: LevelsPtr<'t>) -> Sig {\n        if self.env.has_temp_ext() {\n            return Sig::ALL_RELEVANT;\n        }"""
new="""    pub(crate) fn sig_of(&mut self, _name: NamePtr<'t>, _levels: LevelsPtr<'t>) -> Sig {\n        return Sig::ALL_RELEVANT;\n        #[allow(unreachable_code)]\n        if self.env.has_temp_ext() {\n            return Sig::ALL_RELEVANT;\n        }"""
assert s.count(old)==1; p.write_text(s.replace(old,new,1))
PY

cat >/tmp/v43-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

for d in /tmp/v43-base /tmp/v43-abl; do
  (cd "$d" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
done
cp /tmp/v43-base/target/release/sokonanoda /tmp/v43-base-bin
cp /tmp/v43-abl/target/release/sokonanoda /tmp/v43-abl-bin

for t in std cedar; do
  /tmp/v43-base-bin /tmp/v43-config.json < "/tmp/v43-arena/_build/tests/$t.ndjson" >"/tmp/v43-$t-base.out" 2>"/tmp/v43-$t-base.err"
  /tmp/v43-abl-bin /tmp/v43-config.json < "/tmp/v43-arena/_build/tests/$t.ndjson" >"/tmp/v43-$t-abl.out" 2>"/tmp/v43-$t-abl.err"
  cmp "/tmp/v43-$t-base.out" "/tmp/v43-$t-abl.out"
  echo "V43_${t^^}_SEMANTIC_REPLAY=EXACT"
  for arm in base abl abl base; do
    n=$(find /tmp -maxdepth 1 -type f -name "v43-${t}-${arm}-*.time" | wc -l); n=$((n+1))
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v43-${t}-${arm}-${n}.time" "/tmp/v43-$arm-bin" /tmp/v43-config.json < "/tmp/v43-arena/_build/tests/$t.ndjson" >/dev/null 2>"/tmp/v43-${t}-${arm}-${n}.err"
  done
done

python3 - <<'PY' | tee /tmp/v43-decision.txt
from pathlib import Path
import statistics

def med(t,a):
    xs=[]
    for p in Path('/tmp').glob(f'v43-{t}-{a}-*.time'):
        e,u,s,r=p.read_text().split(); xs.append((float(e),float(u)+float(s),int(r)))
    return statistics.median(x[0] for x in xs), statistics.median(x[1] for x in xs)
score=[]
for t in ('std','cedar'):
    bw,bc=med(t,'base'); aw,ac=med(t,'abl'); d=(aw-bw)/bw*100
    score.append(aw/bw)
    print(f'V43_{t.upper()}_BASE_WALL={bw:.3f} ABL_WALL={aw:.3f} DELTA={d:+.3f}%')
    print(f'V43_{t.upper()}_BASE_CPU={bc:.3f} ABL_CPU={ac:.3f}')
mean=(sum(score)/len(score)-1)*100
print(f'V43_MEAN_NORMALIZED_DELTA={mean:+.3f}%')
if mean <= -2:
    print('DECISION=V43_RELEVANCE_IS_NET_TAX__ADVANCE_DIRECT_MINIMAL_DEPENDENCY_REPRESENTATION')
elif mean < 0:
    print('DECISION=V43_RELEVANCE_WEAK_NET_TAX__DECOMPOSE_SAVINGS_VS_ANALYSIS_COST')
elif mean <= 2:
    print('DECISION=V43_RELEVANCE_NEAR_BREAKEVEN__REDESIGN_ONLY_IF_OBJECT_ELIMINATION_IS_NEAR_ZERO_COST')
else:
    print('DECISION=V43_RELEVANCE_PAYS_FOR_ITSELF__PRESERVE_INFORMATION_AND_ELIMINATE_ANALYSIS_OBJECTS')
print('RULE=ALL_RELEVANT_IS_CONSERVATIVE__NO_IGNORABILITY_CLAIMS')
PY
