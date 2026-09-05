#!/usr/bin/env bash
set -euxo pipefail

SOKO=7b51784fe4ec9b82bf7a20c71ba6bf803a4ed7c0
ROOT=/tmp/v63
rm -rf "$ROOT"
mkdir -p "$ROOT"

git clone https://github.com/intgrah/sokonanoda "$ROOT/incumbent"
git -C "$ROOT/incumbent" checkout "$SOKO"
cp -a "$ROOT/incumbent" "$ROOT/candidate"

# Reconstruct promoted incumbent in both arms: Pi force fast path + relevance propagation-off.
patch_incumbent() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])

p=root/'src/eval.rs'; s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))

p=root/'src/relevance.rs'; s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
assert s.count(old)==1
p.write_text(s.replace(old,'                let _ = r;',1))
PY
}
patch_incumbent "$ROOT/incumbent"
patch_incumbent "$ROOT/candidate"

# v63 candidate: eval() already keys env for Lambda/Pi before eval_no_cache.
# Remove the second key_env call inside those branches only.
python3 - "$ROOT/candidate" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/eval.rs'
s=p.read_text()
old='''            Expr::Lambda { binder_name, binder_style, binder_type, body, .. } =>\n                {\n                let ce = self.key_env(env, e);\n                value::mk_lam(self.arena, binder_name, binder_style, binder_type, Closure::mk_eval(ce, body))\n            }\n            Expr::Pi { binder_name, binder_style, binder_type, body, .. } => {\n                let dom = self.eval(depth, env, binder_type);\n                {\n                    let ce = self.key_env(env, e);\n                    value::mk_pi(self.arena, binder_name, binder_style, dom, Closure::mk_eval(ce, body))\n                }\n            }'''
new='''            Expr::Lambda { binder_name, binder_style, binder_type, body, .. } =>\n                value::mk_lam(self.arena, binder_name, binder_style, binder_type, Closure::mk_eval(env, body)),\n            Expr::Pi { binder_name, binder_style, binder_type, body, .. } => {\n                let dom = self.eval(depth, env, binder_type);\n                value::mk_pi(self.arena, binder_name, binder_style, dom, Closure::mk_eval(env, body))\n            }'''
assert s.count(old)==1, 'expected Lambda/Pi block not found exactly once'
p.write_text(s.replace(old,new,1))
PY

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
ARENA=$(git -C "$ROOT/arena" rev-parse HEAD)
echo "V63_ARENA_HEAD=$ARENA"
cd "$ROOT/arena"
for t in init-prelude std cedar mathlib; do nix develop -c ./lka.py build-test "$t"; done

build_arm() {
  local arm="$1" dir="$2"
  cd "$dir"
  rm -rf pgo target && mkdir pgo
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$PWD/pgo" cargo build --release --locked
  ./target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
  nix shell nixpkgs#llvmPackages_21.llvm -c llvm-profdata merge -o "$PWD/pgo/merged.profdata" "$PWD/pgo"
  rm -rf target
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=$PWD/pgo/merged.profdata" cargo build --release --locked
  cp target/release/sokonanoda "$ROOT/$arm.bin"
}
build_arm incumbent "$ROOT/incumbent"
build_arm candidate "$ROOT/candidate"

mkdir -p "$ROOT/out"
for t in std cedar mathlib; do
  "$ROOT/incumbent.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" > "$ROOT/out/incumbent-$t.out"
  "$ROOT/candidate.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" > "$ROOT/out/candidate-$t.out"
  cmp "$ROOT/out/incumbent-$t.out" "$ROOT/out/candidate-$t.out"
  echo "V63_${t^^}_SEMANTIC_REPLAY=EXACT"
done

: > "$ROOT/timings.csv"
echo 'pass,test,arm,seconds' >> "$ROOT/timings.csv"
orders=("incumbent candidate" "candidate incumbent" "incumbent candidate" "candidate incumbent" "incumbent candidate")
for pass in 1 2 3 4 5; do
  order=${orders[$((pass-1))]}
  for t in cedar mathlib; do
    for arm in $order; do
      sec=$(/usr/bin/time -f '%e' -o "$ROOT/time.tmp" "$ROOT/$arm.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" >/dev/null; cat "$ROOT/time.tmp")
      echo "$pass,$t,$arm,$sec" | tee -a "$ROOT/timings.csv"
    done
  done
done

python3 - <<'PY' | tee "$ROOT/summary.txt"
import csv, math, statistics
from collections import defaultdict
rows=list(csv.DictReader(open('/tmp/v63/timings.csv')))
d=defaultdict(list)
for r in rows: d[(r['test'],r['arm'])].append(float(r['seconds']))
deltas=[]
for t in ('cedar','mathlib'):
    a=d[(t,'incumbent')]; b=d[(t,'candidate')]
    ma=statistics.median(a); mb=statistics.median(b)
    delta=(mb/ma-1)*100
    deltas.append(delta)
    print(f'V63_{t.upper()}_INCUMBENT_RUNS={a}')
    print(f'V63_{t.upper()}_CANDIDATE_RUNS={b}')
    print(f'V63_{t.upper()}_INCUMBENT_MEDIAN={ma:.3f}')
    print(f'V63_{t.upper()}_CANDIDATE_MEDIAN={mb:.3f}')
    print(f'V63_{t.upper()}_DELTA_PCT={delta:.4f}')
geo=(math.prod([1+x/100 for x in deltas])**(1/len(deltas))-1)*100
print(f'V63_PAIR_GEOMEAN_DELTA_PCT={geo:.4f}')
if geo <= -1.0 and max(deltas) <= 0.5:
    print('DECISION=V63_REKEY_BYPASS_MATERIAL__COMPOUND_ON_PROMOTED_INCUMBENT')
elif geo <= -0.5 and max(deltas) <= 0.5:
    print('DECISION=V63_REKEY_BYPASS_WEAK_POSITIVE__REPEAT_BEFORE_COMPOUND')
else:
    print('DECISION=V63_REKEY_BYPASS_NOT_MATERIAL__KILL_AND_DECOMPOSE_NEXT_EVAL_PATH')
print('RULE=REMOVE_ONLY_PROVABLY_REDUNDANT_REPRESENTATION_WORK__EXACT_REPLAY_REQUIRED')
PY
