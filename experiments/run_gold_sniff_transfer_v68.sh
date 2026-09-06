#!/usr/bin/env bash
set -euo pipefail
SOKO=7b51784fe4ec9b82bf7a20c71ba6bf803a4ed7c0
ROOT=/tmp/v68
rm -rf "$ROOT" && mkdir -p "$ROOT"
git clone -q https://github.com/intgrah/sokonanoda "$ROOT/incumbent"
git -C "$ROOT/incumbent" checkout -q "$SOKO"
for arm in beta iota pidemand lookup4; do cp -a "$ROOT/incumbent" "$ROOT/$arm"; done
patch_incumbent(){ python3 - "$1" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/'src/eval.rs'; s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1; p.write_text(s.replace(old,new,1))
p=root/'src/relevance.rs'; s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
assert s.count(old)==1; p.write_text(s.replace(old,'                let _ = r;',1))
PY
}
for arm in incumbent beta iota pidemand lookup4; do patch_incumbent "$ROOT/$arm"; done
curl -fsSL https://raw.githubusercontent.com/metalogiclabs/mathgraph-lean-kernel/mathgraph-infer-beta-fusion/scripts/apply_infer_beta_fusion.py -o "$ROOT/beta.py"
python3 "$ROOT/beta.py" "$ROOT/beta"
curl -fsSL https://raw.githubusercontent.com/metalogiclabs/mathgraph-lean-kernel/mathgraph-iota-apply-fusion/scripts/apply_iota_apply_fusion.py -o "$ROOT/iota.py"
python3 "$ROOT/iota.py" "$ROOT/iota"
curl -fsSL https://raw.githubusercontent.com/metalogiclabs/mathgraph-lean-kernel/mathgraph-infer-pi-demand-bypass/scripts/apply_infer_pi_bypass.py -o "$ROOT/pidemand.py"
python3 "$ROOT/pidemand.py" "$ROOT/pidemand"
curl -fsSL https://raw.githubusercontent.com/metalogiclabs/mathgraph-lean-kernel/mathgraph-infer-pi-demand-bypass/scripts/apply_lookup_unroll.py -o "$ROOT/lookup.py"
python3 "$ROOT/lookup.py" "$ROOT/lookup4" 4
cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
git clone -q --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
echo V68_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)
cd "$ROOT/arena"
for t in init-prelude std; do nix develop -c ./lka.py build-test "$t" >/dev/null; done
build(){ arm=$1; cd "$ROOT/$arm"; RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q; cp target/release/sokonanoda "$ROOT/$arm.bin"; }
for arm in incumbent beta iota pidemand lookup4; do build "$arm"; done
mkdir -p "$ROOT/out"
"$ROOT/incumbent.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/std.ndjson" > "$ROOT/out/incumbent.out"
echo 'arm,pass,seconds' > "$ROOT/timings.csv"
for arm in beta iota pidemand lookup4; do
  "$ROOT/$arm.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/std.ndjson" > "$ROOT/out/$arm.out"
  cmp "$ROOT/out/incumbent.out" "$ROOT/out/$arm.out" && echo "V68_${arm^^}_STD_REPLAY=EXACT"
  for pass in 1 2 3; do sec=$(/usr/bin/time -f '%e' -o "$ROOT/t" "$ROOT/$arm.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/std.ndjson" >/dev/null; cat "$ROOT/t"); echo "$arm,$pass,$sec" >> "$ROOT/timings.csv"; done
done
for pass in 1 2 3; do sec=$(/usr/bin/time -f '%e' -o "$ROOT/t" "$ROOT/incumbent.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/std.ndjson" >/dev/null; cat "$ROOT/t"); echo "incumbent,$pass,$sec" >> "$ROOT/timings.csv"; done
python3 - <<'PY' | tee "$ROOT/summary.txt"
import csv,statistics
rows=list(csv.DictReader(open('/tmp/v68/timings.csv')))
d={}
for a in {r['arm'] for r in rows}: d[a]=statistics.median(float(r['seconds']) for r in rows if r['arm']==a)
base=d['incumbent']
print(f'V68_INCUMBENT_STD_MEDIAN={base:.3f}')
best=None
for a in ('beta','iota','pidemand','lookup4'):
    delta=(d[a]/base-1)*100
    print(f'V68_{a.upper()}_STD_MEDIAN={d[a]:.3f}')
    print(f'V68_{a.upper()}_DELTA_PCT={delta:.4f}')
    if best is None or delta<best[1]: best=(a,delta)
print(f'V68_BEST={best[0]}')
print(f'V68_BEST_DELTA_PCT={best[1]:.4f}')
if best[1] <= -3.0: print('DECISION=V68_BIG_SIGNAL__FULL_GATE_SINGLE_WINNER')
else: print('DECISION=V68_NO_BIG_SIGNAL__STOP_AND_SHIP_V61')
print('RULE=ONLY_PAY_MATHLIB_FOR_GE3PCT_STD_SIGNAL')
PY
