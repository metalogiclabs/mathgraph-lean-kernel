#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v59-*

for arm in incumbent quotient; do
  git worktree add "/tmp/v59-$arm" "$BASE"
  python3 - "$arm" "/tmp/v59-$arm" <<'PY'
from pathlib import Path
import sys
arm=sys.argv[1]; root=Path(sys.argv[2])

# Frozen semantic incumbent: Pi fast path + relevance propagation-off.
p=root/'src/eval.rs'; s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))

p=root/'src/relevance.rs'; s=p.read_text()
prop_loop='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
assert s.count(prop_loop)==1
s=s.replace(prop_loop,'                let _ = r;',1)
p.write_text(s)

if arm == 'quotient':
    s=p.read_text()
    old='''    pub(crate) absent_arg: u64,\n    pub(crate) prop_result: u64,\n    pub(crate) result_known: u64,'''
    new='''    pub(crate) absent_arg: u64,\n    pub(crate) result_not_proof: bool,'''
    assert s.count(old)==1
    s=s.replace(old,new,1)
    old='''        Sig { arity: 0, prop_arg: 0, arg_known: 0, absent_arg: 0, prop_result: 0, result_known: 0 };'''
    new='''        Sig { arity: 0, prop_arg: 0, arg_known: 0, absent_arg: 0, result_not_proof: false };'''
    assert s.count(old)==1
    s=s.replace(old,new,1)
    old='''    pub(crate) fn result_is_not_proof(&self, k: u32) -> bool {\n        k < MAX_TRACKED && (self.result_known >> k) & 1 == 1 && (self.prop_result >> k) & 1 == 0\n    }'''
    new='''    pub(crate) fn result_is_not_proof(&self, k: u32) -> bool {\n        k == u32::from(self.arity) && self.result_not_proof\n    }'''
    assert s.count(old)==1
    s=s.replace(old,new,1)
    old='''        let mut prop_result = 0u64;\n        let mut result_known = 0u64;\n        if let Some(term) = terminal {\n            if let Some(sb) = self.level_of_type(depth, term) {\n                let mut r = sb;\n                if n < MAX_TRACKED as usize {\n                    result_known |= 1u64 << n;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << n;\n                    }\n                }\n                let _ = r;\n            }\n        }'''
    new='''        let result_not_proof = if let Some(term) = terminal {\n            if let Some(sb) = self.level_of_type(depth, term) {\n                !self.ctx.is_zero(sb)\n            } else {\n                false\n            }\n        } else {\n            false\n        };'''
    assert s.count(old)==1
    s=s.replace(old,new,1)
    old='''            absent_arg: self.absent_args(name),\n            prop_result,\n            result_known,'''
    new='''            absent_arg: self.absent_args(name),\n            result_not_proof,'''
    assert s.count(old)==1
    s=s.replace(old,new,1)
    p.write_text(s)
PY
done

cat >/tmp/v59-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v59-arena
cd /tmp/v59-arena
for t in init-prelude std cedar; do nix develop -c ./lka.py build-test "$t"; done

# Match the Arena-style init-prelude PGO used by v58, independently per arm.
for arm in incumbent quotient; do
  mkdir -p "/tmp/v59-$arm-pgo"
  (cd "/tmp/v59-$arm" && RUSTFLAGS="-C target-cpu=native -Cprofile-generate=/tmp/v59-$arm-pgo" cargo build --release --locked)
  "/tmp/v59-$arm/target/release/sokonanoda" /tmp/v59-config.json < /tmp/v59-arena/_build/tests/init-prelude.ndjson >/dev/null 2>"/tmp/v59-$arm-train.err"
  llvm-profdata merge -o "/tmp/v59-$arm-pgo/merged.profdata" "/tmp/v59-$arm-pgo"
  (cd "/tmp/v59-$arm" && RUSTFLAGS="-C target-cpu=native -Cprofile-use=/tmp/v59-$arm-pgo/merged.profdata" cargo build --release --locked)
  cp "/tmp/v59-$arm/target/release/sokonanoda" "/tmp/v59-$arm-bin"
done

for t in std cedar; do
  /tmp/v59-incumbent-bin /tmp/v59-config.json < "/tmp/v59-arena/_build/tests/$t.ndjson" >"/tmp/v59-$t-incumbent.out" 2>"/tmp/v59-$t-incumbent.err"
  /tmp/v59-quotient-bin /tmp/v59-config.json < "/tmp/v59-arena/_build/tests/$t.ndjson" >"/tmp/v59-$t-quotient.out" 2>"/tmp/v59-$t-quotient.err"
  cmp "/tmp/v59-$t-incumbent.out" "/tmp/v59-$t-quotient.out"
  echo "V59_${t^^}_SEMANTIC_REPLAY=EXACT"

  orders=("incumbent quotient" "quotient incumbent" "incumbent quotient")
  r=0
  for order in "${orders[@]}"; do
    r=$((r+1))
    for arm in $order; do
      /usr/bin/time -f '%e %U %S %M' -o "/tmp/v59-$t-$arm-$r.time" \
        "/tmp/v59-$arm-bin" /tmp/v59-config.json < "/tmp/v59-arena/_build/tests/$t.ndjson" >/dev/null 2>"/tmp/v59-$t-$arm-$r.err"
    done
  done
done

python3 - <<'PY' | tee /tmp/v59-decision.txt
from pathlib import Path
from statistics import median
ratios=[]; deltas=[]
for t in ('std','cedar'):
    vals={}
    for arm in ('incumbent','quotient'):
        xs=[float(Path(f'/tmp/v59-{t}-{arm}-{r}.time').read_text().split()[0]) for r in range(1,4)]
        vals[arm]=median(xs)
        print(f'V59_{t.upper()} arm={arm} raw={xs} median={vals[arm]:.3f}')
    d=(vals['quotient']/vals['incumbent']-1)*100
    deltas.append(d); ratios.append(vals['quotient']/vals['incumbent'])
    print(f'V59_{t.upper()}_DELTA_QUOTIENT_VS_INCUMBENT={d:+.4f}%')
mean=(sum(ratios)/len(ratios)-1)*100
print(f'V59_MEAN_NORMALIZED_DELTA={mean:+.4f}% deltas={[round(x,4) for x in deltas]}')
if mean <= -2.0 and all(d < 0 for d in deltas):
    print('DECISION=V59_TRANSFER_SIGNAL_MATERIAL__REPEAT_MATHLIB_BEFORE_PROMOTION')
elif all(d < 0 for d in deltas) and mean <= -1.0:
    print('DECISION=V59_TRANSFER_SIGNAL_WEAK_CONSISTENT__ONE_FINAL_MATHLIB_CONFIRMATION_ONLY')
else:
    print('DECISION=V59_NO_TRANSFER_SIGNAL__KILL_TERMINAL_MASK_QUOTIENT')
print('RULE=WEAK_MATHLIB_EFFECT_REQUIRES_CROSS_WORKLOAD_DIRECTIONAL_SUPPORT_BEFORE_RETENTION')
PY
