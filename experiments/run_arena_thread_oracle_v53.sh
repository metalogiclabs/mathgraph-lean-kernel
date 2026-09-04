#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v53-src /tmp/v53-arena /tmp/v53-*.time /tmp/v53-*.out /tmp/v53-*.err
git worktree add /tmp/v53-src "$BASE"

# Current verified semantic incumbent: Pi-only + relevance backward-result propagation off.
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v53-src/src/eval.rs'); s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))

p=Path('/tmp/v53-src/src/relevance.rs'); s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
new='''                let _ = r;'''
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY

(cd /tmp/v53-src && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
cp /tmp/v53-src/target/release/sokonanoda /tmp/v53-bin

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v53-arena
cd /tmp/v53-arena
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t"; done

for n in 1 2 4; do
cat >"/tmp/v53-config-$n.json" <<EOF
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":$n,"print_success_message":false}
EOF
done

# Semantic replay: thread count must not affect checker output.
for t in std cedar mathlib; do
  for n in 1 2 4; do
    /tmp/v53-bin "/tmp/v53-config-$n.json" < "_build/tests/$t.ndjson" >"/tmp/v53-$t-$n.out" 2>"/tmp/v53-$t-$n.err"
  done
  cmp "/tmp/v53-$t-1.out" "/tmp/v53-$t-2.out"
  cmp "/tmp/v53-$t-1.out" "/tmp/v53-$t-4.out"
  echo "V53_${t^^}_SEMANTIC_REPLAY=EXACT"
done

# Alternate order to limit thermal/order bias. Three repeats on small/medium, two on Mathlib.
for t in std cedar; do
  orders=("1 2 4" "4 2 1" "2 1 4")
  r=0
  for order in "${orders[@]}"; do
    r=$((r+1))
    for n in $order; do
      /usr/bin/time -f '%e %U %S %M' -o "/tmp/v53-$t-$n-$r.time" \
        /tmp/v53-bin "/tmp/v53-config-$n.json" < "_build/tests/$t.ndjson" >/dev/null 2>"/tmp/v53-$t-$n-$r.err"
    done
  done
done
orders=("1 2 4" "4 2 1")
r=0
for order in "${orders[@]}"; do
  r=$((r+1))
  for n in $order; do
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v53-mathlib-$n-$r.time" \
      /tmp/v53-bin "/tmp/v53-config-$n.json" < _build/tests/mathlib.ndjson >/dev/null 2>"/tmp/v53-mathlib-$n-$r.err"
  done
done

python3 - <<'PY' | tee /tmp/v53-decision.txt
from pathlib import Path
from statistics import median
wins={}
for t in ('std','cedar','mathlib'):
    vals={}
    for n in (1,2,4):
        xs=[float(p.read_text().split()[0]) for p in sorted(Path('/tmp').glob(f'v53-{t}-{n}-*.time'))]
        vals[n]=median(xs)
        print(f'V53_{t.upper()}_THREADS_{n} raw={xs} median={vals[n]:.3f}')
    w=min(vals,key=vals.get); wins[t]=w
    print(f'V53_{t.upper()}_WINNER_THREADS={w}')
    print(f'V53_{t.upper()}_FIXED4_ORACLE_GAP={(vals[4]/vals[w]-1)*100:+.3f}%')
print('V53_WINNERS '+ ' '.join(f'{k}={v}' for k,v in wins.items()))
if len(set(wins.values()))>1:
    print('DECISION=V53_WORKLOAD_DEPENDENT_THREADING_FORCED__DERIVE_MINIMAL_SEPARATOR')
elif next(iter(wins.values()))==4:
    print('DECISION=V53_FIXED4_SUPPORTED_ON_TESTED_ARENA_CLASSES__DO_NOT_ADD_ADAPTIVE_POLICY')
else:
    print('DECISION=V53_GLOBAL_THREAD_COUNT_CHANGE_CANDIDATE__FULL_ARENA_GATE')
print('RULE=CREATE_THREAD_POLICY_DISTINCTIONS_ONLY_IF_ORACLE_WINNERS_DIFFER')
PY
