#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v58-*

for arm in incumbent quotient; do
  git worktree add "/tmp/v58-$arm" "$BASE"
  python3 - "$arm" "/tmp/v58-$arm" <<'PY'
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

cat >/tmp/v58-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v58-arena
cd /tmp/v58-arena
for t in init-prelude mathlib; do nix develop -c ./lka.py build-test "$t"; done

# Arena-style init-prelude PGO independently for each arm.
for arm in incumbent quotient; do
  mkdir -p "/tmp/v58-$arm-pgo"
  (cd "/tmp/v58-$arm" && RUSTFLAGS="-C target-cpu=native -Cprofile-generate=/tmp/v58-$arm-pgo" cargo build --release --locked)
  "/tmp/v58-$arm/target/release/sokonanoda" /tmp/v58-config.json < /tmp/v58-arena/_build/tests/init-prelude.ndjson >/dev/null 2>"/tmp/v58-$arm-train.err"
  llvm-profdata merge -o "/tmp/v58-$arm-pgo/merged.profdata" "/tmp/v58-$arm-pgo"
  (cd "/tmp/v58-$arm" && RUSTFLAGS="-C target-cpu=native -Cprofile-use=/tmp/v58-$arm-pgo/merged.profdata" cargo build --release --locked)
  cp "/tmp/v58-$arm/target/release/sokonanoda" "/tmp/v58-$arm-bin"
done

# Exact semantic replay is mandatory.
/tmp/v58-incumbent-bin /tmp/v58-config.json < /tmp/v58-arena/_build/tests/mathlib.ndjson >/tmp/v58-incumbent.out 2>/tmp/v58-incumbent.err
/tmp/v58-quotient-bin /tmp/v58-config.json < /tmp/v58-arena/_build/tests/mathlib.ndjson >/tmp/v58-quotient.out 2>/tmp/v58-quotient.err
cmp /tmp/v58-incumbent.out /tmp/v58-quotient.out
echo V58_MATHLIB_SEMANTIC_REPLAY=EXACT

# Three balanced alternating Mathlib passes.
orders=("incumbent quotient" "quotient incumbent" "incumbent quotient")
r=0
for order in "${orders[@]}"; do
  r=$((r+1))
  for arm in $order; do
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v58-$arm-$r.time" \
      "/tmp/v58-$arm-bin" /tmp/v58-config.json < /tmp/v58-arena/_build/tests/mathlib.ndjson >/dev/null 2>"/tmp/v58-$arm-$r.err"
  done
done

python3 - <<'PY' | tee /tmp/v58-decision.txt
from pathlib import Path
from statistics import median
raw={}
med={}
for arm in ('incumbent','quotient'):
    xs=[float(Path(f'/tmp/v58-{arm}-{r}.time').read_text().split()[0]) for r in range(1,4)]
    raw[arm]=xs; med[arm]=median(xs)
    print(f'V58_TIMES arm={arm} raw={xs} median={med[arm]:.3f}')
d=(med['quotient']/med['incumbent']-1)*100
wins=sum(q < i for q,i in zip(raw['quotient'],raw['incumbent']))
paired=[(q/i-1)*100 for q,i in zip(raw['quotient'],raw['incumbent'])]
print(f'V58_DELTA_QUOTIENT_VS_INCUMBENT={d:+.4f}% pass_wins_quotient={wins}/3 paired_deltas={[round(x,4) for x in paired]}')
if d <= -2.0 and wins >= 2:
    print('DECISION=V58_TERMINAL_MASK_QUOTIENT_PROMOTE__RESULT_POSITION_MASKS_NOT_NEEDED_AFTER_PROPAGATION_OFF')
elif d >= 2.0:
    print('DECISION=V58_TERMINAL_MASK_QUOTIENT_KILL__REPRESENTATION_COMPRESSION_NOT_ECONOMIC')
else:
    print('DECISION=V58_TERMINAL_MASK_QUOTIENT_WEAK__DO_NOT_RETAIN_WITHOUT_TRANSFER_SIGNAL')
PY
