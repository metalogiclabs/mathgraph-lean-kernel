#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ROOT=/tmp/v80
rm -rf "$ROOT" && mkdir -p "$ROOT"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
cp -a "$ROOT/base" "$ROOT/winner"
cp -a "$ROOT/base" "$ROOT/trap"
cp -a "$ROOT/base" "$ROOT/samework"

python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
anchor="""    fn spine_type_with_value(&mut self, depth: u32, mut ty: V<'t>, prev_head: V<'t>, spine: S<'t>) -> V<'t> {\n        let mut prev = prev_head;\n        for elim in spine.to_vec() {\n"""
old='''                ElimView::App(a) => {\n                    let ty_f = self.force_all(depth, ty);\n'''

def patch(name, helper_name, body):
    p=root/name/'src/eval.rs'; s=p.read_text()
    helper=f"""    #[inline]\n    fn {helper_name}(&mut self, depth: u32, v: V<'t>, app_pos: usize) -> V<'t> {{\n{body}    }}\n\n"""
    assert s.count(anchor)==1 and s.count(old)==1
    s=s.replace(anchor, helper+"""    fn spine_type_with_value(&mut self, depth: u32, mut ty: V<'t>, prev_head: V<'t>, spine: S<'t>) -> V<'t> {\n        let mut prev = prev_head;\n        let mut app_pos = 0usize;\n        for elim in spine.to_vec() {\n""",1)
    s=s.replace(old,f'''                ElimView::App(a) => {{\n                    let ty_f = self.{helper_name}(depth, ty, app_pos);\n                    app_pos += 1;\n''',1)
    p.write_text(s)

patch('winner','force_pi_for_spine_v80_winner',"""        let first = app_pos == 0;\n        match v {\n            Value::Pi { .. } => v,\n            Value::NatLit { .. } | Value::StrLit { .. } if !first => v,\n            _ => self.force_all(depth, v),\n        }\n""")

patch('trap','force_pi_for_spine_v80_trap',"""        let first = app_pos == 0;\n        match v {\n            Value::NatLit { .. } | Value::StrLit { .. } if !first => {\n                panic!(\"V80_TRAP_HIT\")\n            }\n            _ => self.force_all(depth, v),\n        }\n""")

patch('samework','force_pi_for_spine_v80_samework',"""        let first = app_pos == 0;\n        match v {\n            Value::NatLit { .. } | Value::StrLit { .. } if !first => self.force_all(depth, v),\n            _ => self.force_all(depth, v),\n        }\n""")
PY

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
echo V80_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done

build(){ arm=$1; cd "$ROOT/$arm"; RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q; cp target/release/sokonanoda "$ROOT/$arm.bin"; }
for arm in base winner trap samework; do build "$arm"; done

mkdir -p "$ROOT/out" "$ROOT/disasm"
: > "$ROOT/summary.txt"
echo 'HYPOTHESIS=V77_GAIN_IS_STATIC_CODEGEN_OR_LAYOUT_NOT_SEMANTIC_BYPASS' | tee -a "$ROOT/summary.txt"
echo 'TEST=MATCHED_ZERO_HIT_CODE_SHAPE_TOURNAMENT' | tee -a "$ROOT/summary.txt"

# Exact replay first. v79 established the predicate has zero semantic hits; repeat here.
for corpus in std cedar mathlib; do
  "$ROOT/base.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/base-$corpus.out"
  for arm in winner trap samework; do
    "$ROOT/$arm.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/$arm-$corpus.out" 2>"$ROOT/out/$arm-$corpus.err"
    cmp "$ROOT/out/base-$corpus.out" "$ROOT/out/$arm-$corpus.out"
    if grep -q 'V80_TRAP_HIT' "$ROOT/out/$arm-$corpus.err"; then
      echo "UNEXPECTED_ATTACHMENT_HIT arm=$arm corpus=$corpus" >&2
      exit 9
    fi
  done
  echo "V80_${corpus^^}_ALL_ARMS_REPLAY=EXACT" | tee -a "$ROOT/summary.txt"
done

# Static fingerprints: any observed speed difference with exact identical execution
# must be attributed to code generation/layout or measurement noise.
printf 'arm,bytes,sha256,text_bytes\n' > "$ROOT/binary_fingerprints.csv"
for arm in base winner trap samework; do
  bytes=$(stat -c %s "$ROOT/$arm.bin")
  sha=$(sha256sum "$ROOT/$arm.bin" | awk '{print $1}')
  text=$(size -A "$ROOT/$arm.bin" | awk '$1==".text"{print $2; exit}')
  printf '%s,%s,%s,%s\n' "$arm" "$bytes" "$sha" "${text:-NA}" >> "$ROOT/binary_fingerprints.csv"
  objdump -d -C "$ROOT/$arm.bin" | grep -A120 -B10 'spine_type_with_value' > "$ROOT/disasm/$arm-spine.txt" || true
done
cat "$ROOT/binary_fingerprints.csv" | tee -a "$ROOT/summary.txt"

# Balanced 5-pass timing. Rotate arm order each pass to reduce temporal bias.
printf 'pass,corpus,arm,seconds\n' > "$ROOT/timings.csv"
arms=(base winner trap samework)
for pass in 1 2 3 4 5; do
  shift=$(( (pass-1) % 4 ))
  order=( ${arms[@]:$shift} ${arms[@]:0:$shift} )
  for corpus in std cedar mathlib; do
    for arm in "${order[@]}"; do
      sec=$({ /usr/bin/time -f '%e' "$ROOT/$arm.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > /dev/null; } 2>&1 | tail -n1)
      printf '%s,%s,%s,%s\n' "$pass" "$corpus" "$arm" "$sec" | tee -a "$ROOT/timings.csv"
    done
  done
done

python3 - "$ROOT" <<'PY' | tee -a "$ROOT/summary.txt"
import csv, math, statistics, sys
from pathlib import Path
root=Path(sys.argv[1])
rows=list(csv.DictReader(open(root/'timings.csv')))
corpora=['std','cedar','mathlib']
arms=['base','winner','trap','samework']
med={}
for c in corpora:
    for a in arms:
        xs=[float(r['seconds']) for r in rows if r['corpus']==c and r['arm']==a]
        med[c,a]=statistics.median(xs)
print('MEDIANS_SECONDS')
for c in corpora:
    print(c, *(f'{a}={med[c,a]:.6f}' for a in arms))
print('DELTAS_VS_BASE_PERCENT')
geo={}
for a in arms[1:]:
    ds=[]
    for c in corpora:
        d=(med[c,a]/med[c,'base']-1.0)*100.0
        ds.append(d)
        print(f'{a} {c} {d:+.3f}%')
    ratios=[med[c,a]/med[c,'base'] for c in corpora]
    geo[a]=(math.prod(ratios)**(1/len(ratios))-1)*100
    print(f'{a} GEOMEAN {geo[a]:+.3f}%')

# Decision focuses on whether a zero-hit control shares a material gain with winner.
w=geo['winner']; controls=[geo['trap'],geo['samework']]
if w <= -1.0 and any(x <= -1.0 for x in controls):
    print('DECISION=CODE_LAYOUT_CAUSALITY_SUPPORTED__ZERO_HIT_CONTROL_REPRODUCES_GAIN')
elif w <= -1.0 and all(abs(x) < 0.75 for x in controls):
    print('DECISION=WINNER_STATIC_CODEGEN_EFFECT_SPECIFIC__INSPECT_DISASSEMBLY_AND_LAYOUT_DIFF')
elif abs(w) < 1.0:
    print('DECISION=V77_GAIN_NOT_STABLE_UNDER_V80_REPLAY__TREAT_AS_MEASUREMENT_OR_BUILD_VARIANCE')
else:
    print('DECISION=MIXED__STATIC_CAUSALITY_NOT_YET_ISOLATED')
PY

cat "$ROOT/summary.txt"
