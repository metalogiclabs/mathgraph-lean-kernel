#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v46-base /tmp/v46-arg /tmp/v46-result /tmp/v46-arena

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v46-arena
(cd /tmp/v46-arena && for t in std cedar; do nix develop -c ./lka.py build-test "$t"; done)

for arm in base arg result; do git worktree add "/tmp/v46-$arm" "$BASE"; done

# Pi-only verified incumbent in every arm.
for d in /tmp/v46-base /tmp/v46-arg /tmp/v46-result; do
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

# ARG-OFF: preserve telescope traversal and typed fresh BVars, but stop computing
# binder-domain level/relevance facts. Unknown means conservatively relevant.
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v46-arg/src/relevance.rs'); s=p.read_text()
old='''            let d = *domain;\n            dom.push(self.level_of_type(depth, d));\n            let fresh = self.mk_bvar_hc(depth, d);'''
new='''            let d = *domain;\n            dom.push(None);\n            let fresh = self.mk_bvar_hc(depth, d);'''
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY

# RESULT-OFF: preserve traversal and argument facts, but stop computing terminal
# result-level propagation. Unknown means conservatively no result-based shortcut.
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v46-result/src/relevance.rs'); s=p.read_text()
old='''        let mut prop_result = 0u64;\n        let mut result_known = 0u64;\n        if let Some(term) = terminal {\n            if let Some(sb) = self.level_of_type(depth, term) {\n                let mut r = sb;\n                if n < MAX_TRACKED as usize {\n                    result_known |= 1u64 << n;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << n;\n                    }\n                }\n                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }\n            }\n        }'''
new='''        let prop_result = 0u64;\n        let result_known = 0u64;\n        let _ = terminal;'''
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY

cat >/tmp/v46-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

for arm in base arg result; do
  (cd "/tmp/v46-$arm" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
  cp "/tmp/v46-$arm/target/release/sokonanoda" "/tmp/v46-$arm-bin"
done

for t in std cedar; do
  /tmp/v46-base-bin /tmp/v46-config.json < "/tmp/v46-arena/_build/tests/$t.ndjson" >"/tmp/v46-$t-base.out" 2>"/tmp/v46-$t-base.err"
  for arm in arg result; do
    /tmp/v46-$arm-bin /tmp/v46-config.json < "/tmp/v46-arena/_build/tests/$t.ndjson" >"/tmp/v46-$t-$arm.out" 2>"/tmp/v46-$t-$arm.err"
    cmp "/tmp/v46-$t-base.out" "/tmp/v46-$t-$arm.out"
    echo "V46_${t^^}_${arm^^}_SEMANTIC_REPLAY=EXACT"
  done
  for arm in base arg result result arg base; do
    n=$(find /tmp -maxdepth 1 -type f -name "v46-${t}-${arm}-*.time" | wc -l); n=$((n+1))
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v46-${t}-${arm}-${n}.time" "/tmp/v46-$arm-bin" /tmp/v46-config.json < "/tmp/v46-arena/_build/tests/$t.ndjson" >/dev/null 2>"/tmp/v46-${t}-${arm}-${n}.err"
  done
done

python3 - <<'PY' | tee /tmp/v46-decision.txt
from pathlib import Path
import statistics

def med(t,a):
    xs=[]
    for p in Path('/tmp').glob(f'v46-{t}-{a}-*.time'):
        e,u,s,r=p.read_text().split(); xs.append((float(e),float(u)+float(s),int(r)))
    return statistics.median(x[0] for x in xs), statistics.median(x[1] for x in xs)
means={}
for arm in ('arg','result'):
    ratios=[]
    for t in ('std','cedar'):
        bw,bc=med(t,'base'); aw,ac=med(t,arm); d=(aw-bw)/bw*100
        ratios.append(aw/bw)
        print(f'V46_{t.upper()}_{arm.upper()}_BASE_WALL={bw:.3f} ARM_WALL={aw:.3f} DELTA={d:+.3f}%')
        print(f'V46_{t.upper()}_{arm.upper()}_BASE_CPU={bc:.3f} ARM_CPU={ac:.3f}')
    means[arm]=(sum(ratios)/len(ratios)-1)*100
    print(f'V46_{arm.upper()}_MEAN_NORMALIZED_DELTA={means[arm]:+.3f}%')

# Negative delta means computing that information costs more than it saves downstream.
if means['arg'] <= -2 and means['arg'] < means['result']:
    print('DECISION=V46_ARG_LEVEL_INFORMATION_NET_TAX__REDESIGN_ARG_RELEVANCE_INTERFACE')
elif means['result'] <= -2 and means['result'] < means['arg']:
    print('DECISION=V46_RESULT_INFORMATION_NET_TAX__REDESIGN_RESULT_RECONSTRUCTION')
elif means['arg'] >= 2 and means['result'] >= 2:
    print('DECISION=V46_BOTH_INFORMATION_FAMILIES_PAY__SHARED_TELESCOPE_TRAVERSAL_IS_NEXT_TARGET')
elif means['arg'] >= 2:
    print('DECISION=V46_ARG_INFORMATION_PAYS__RESULT_OR_SHARED_TRAVERSAL_NEXT')
elif means['result'] >= 2:
    print('DECISION=V46_RESULT_INFORMATION_PAYS__ARG_OR_SHARED_TRAVERSAL_NEXT')
else:
    print('DECISION=V46_MARGINALS_NEAR_BREAK_EVEN__PROFILE_SHARED_TELESCOPE_TRAJECTORY')
print('RULE=CONSERVATIVE_UNKNOWN_ONLY__EXACT_REPLAY_REQUIRED__NO_FALSE_IRRELEVANCE')
PY
