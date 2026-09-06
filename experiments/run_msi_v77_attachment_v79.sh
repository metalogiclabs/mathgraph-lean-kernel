#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ROOT=/tmp/v79
rm -rf "$ROOT" && mkdir -p "$ROOT"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
cp -a "$ROOT/base" "$ROOT/winner"
cp -a "$ROOT/base" "$ROOT/trap"

python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
anchor="""    fn spine_type_with_value(&mut self, depth: u32, mut ty: V<'t>, prev_head: V<'t>, spine: S<'t>) -> V<'t> {\n        let mut prev = prev_head;\n        for elim in spine.to_vec() {\n"""
old='''                ElimView::App(a) => {\n                    let ty_f = self.force_all(depth, ty);\n'''

p=root/'winner'/'src/eval.rs'; s=p.read_text()
helper="""    #[inline]\n    fn force_pi_for_spine_v79_winner(&mut self, depth: u32, v: V<'t>, app_pos: usize) -> V<'t> {\n        let first = app_pos == 0;\n        match v {\n            Value::Pi { .. } => v,\n            Value::NatLit { .. } | Value::StrLit { .. } if !first => v,\n            _ => self.force_all(depth, v),\n        }\n    }\n\n"""
assert s.count(anchor)==1 and s.count(old)==1
s=s.replace(anchor, helper+"""    fn spine_type_with_value(&mut self, depth: u32, mut ty: V<'t>, prev_head: V<'t>, spine: S<'t>) -> V<'t> {\n        let mut prev = prev_head;\n        let mut app_pos = 0usize;\n        for elim in spine.to_vec() {\n""",1)
s=s.replace(old,'''                ElimView::App(a) => {\n                    let ty_f = self.force_pi_for_spine_v79_winner(depth, ty, app_pos);\n                    app_pos += 1;\n''',1)
p.write_text(s)

p=root/'trap'/'src/eval.rs'; s=p.read_text()
helper="""    #[inline]\n    fn force_pi_for_spine_v79_trap(&mut self, depth: u32, v: V<'t>, app_pos: usize) -> V<'t> {\n        let first = app_pos == 0;\n        match v {\n            Value::NatLit { .. } | Value::StrLit { .. } if !first => {\n                panic!(\"V79_ATTACHMENT_HIT: v77 NL-later branch is semantically reachable\")\n            }\n            _ => self.force_all(depth, v),\n        }\n    }\n\n"""
assert s.count(anchor)==1 and s.count(old)==1
s=s.replace(anchor, helper+"""    fn spine_type_with_value(&mut self, depth: u32, mut ty: V<'t>, prev_head: V<'t>, spine: S<'t>) -> V<'t> {\n        let mut prev = prev_head;\n        let mut app_pos = 0usize;\n        for elim in spine.to_vec() {\n""",1)
s=s.replace(old,'''                ElimView::App(a) => {\n                    let ty_f = self.force_pi_for_spine_v79_trap(depth, ty, app_pos);\n                    app_pos += 1;\n''',1)
p.write_text(s)
PY

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
echo V79_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done

build(){ arm=$1; cd "$ROOT/$arm"; RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q; cp target/release/sokonanoda "$ROOT/$arm.bin"; }
build base
build winner
build trap

mkdir -p "$ROOT/out"
: > "$ROOT/summary.txt"
echo 'HYPOTHESIS=V77_NL_LATER_SEMANTIC_ATTACHMENT' | tee -a "$ROOT/summary.txt"
echo 'TEST=TRAP_ON_EXACT_WINNING_PREDICATE' | tee -a "$ROOT/summary.txt"

for corpus in std cedar mathlib; do
  "$ROOT/base.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/base-$corpus.out"
  "$ROOT/winner.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/winner-$corpus.out"
  cmp "$ROOT/out/base-$corpus.out" "$ROOT/out/winner-$corpus.out"
  echo "V79_${corpus^^}_WINNER_REPLAY=EXACT" | tee -a "$ROOT/summary.txt"

  set +e
  "$ROOT/trap.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/trap-$corpus.out" 2>"$ROOT/out/trap-$corpus.err"
  rc=$?
  set -e
  if grep -q 'V79_ATTACHMENT_HIT' "$ROOT/out/trap-$corpus.err"; then
    echo "V79_${corpus^^}_ATTACHMENT=HIT" | tee -a "$ROOT/summary.txt"
  elif [ "$rc" -ne 0 ]; then
    echo "V79_${corpus^^}_ATTACHMENT=OTHER_FAILURE_RC_${rc}" | tee -a "$ROOT/summary.txt"
    cat "$ROOT/out/trap-$corpus.err" >&2
    exit "$rc"
  else
    cmp "$ROOT/out/base-$corpus.out" "$ROOT/out/trap-$corpus.out"
    echo "V79_${corpus^^}_ATTACHMENT=ZERO_HITS" | tee -a "$ROOT/summary.txt"
  fi
done

if grep -q 'ATTACHMENT=HIT' "$ROOT/summary.txt"; then
  echo 'DECISION=SEMANTIC_ATTACHMENT_CONFIRMED__MEASURE_HIT_COUNTS_NEXT' | tee -a "$ROOT/summary.txt"
else
  echo 'DECISION=ZERO_SEMANTIC_HITS__V77_GAIN_IS_NOT_FROM_PROPOSED_BYPASS__TEST_CODE_LAYOUT_CAUSALITY_NEXT' | tee -a "$ROOT/summary.txt"
fi
cat "$ROOT/summary.txt"
