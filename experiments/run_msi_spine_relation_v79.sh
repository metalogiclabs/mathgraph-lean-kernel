#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ROOT=/tmp/v79
rm -rf "$ROOT"; mkdir -p "$ROOT/out"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
cp -a "$ROOT/base" "$ROOT/probe"
cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
r=Path(sys.argv[1]);s=(r/'probe/src/eval.rs').read_text()
a="""    fn spine_type_with_value(&mut self, depth: u32, mut ty: V<'t>, prev_head: V<'t>, spine: S<'t>) -> V<'t> {
        let mut prev = prev_head;
        for elim in spine.to_vec() {
"""
b="""                ElimView::App(a) => {
                    let ty_f = self.force_all(depth, ty);
"""
assert s.count(a)==1 and s.count(b)==1
helper="""    fn force_pi_for_spine_v79(&mut self, depth: u32, v: V<'t>, cell: usize) -> V<'t> {
        if matches!(v, Value::NatLit { .. } | Value::StrLit { .. }) {
            V79_COUNTS[cell].fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            let r = self.force_all(depth, v);
            if std::ptr::eq(v, r) {
                V79_COUNTS[cell + 4].fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            }
            r
        } else { self.force_all(depth, v) }
    }

"""
s=s.replace(a,helper+a.replace('        for elim in spine.to_vec() {','        let es = spine.to_vec();\n        let total = es.len();\n        let mut prev_proj = false;\n        for elim in es {'),1)
s=s.replace(b,"""                ElimView::App(a) => {
                    let cell = usize::from(prev_proj) * 2 + usize::from(total > 2);
                    let ty_f = self.force_pi_for_spine_v79(depth, ty, cell);
                    prev_proj = false;
""",1)
start=s.index('    fn spine_type_with_value(',s.index('fn force_pi_for_spine_v79'));end=s.find('\n    fn ',start+5)
if end<0:end=len(s)
seg=s[start:end];needle='ElimView::Proj { ty_name, idx } => {';assert seg.count(needle)==1
seg=seg.replace(needle,needle+'\n                    prev_proj = true;',1)
s=s[:start]+seg+s[end:]
s="""static V79_COUNTS: [std::sync::atomic::AtomicU64; 8] = [const { std::sync::atomic::AtomicU64::new(0) }; 8];
pub fn v79_report() {
    use std::sync::atomic::Ordering;
    for i in 0..4 {
        eprintln!("V79_CELL_{}_HITS={}", i, V79_COUNTS[i].load(Ordering::Relaxed));
        eprintln!("V79_CELL_{}_IDENTITY={}", i, V79_COUNTS[i+4].load(Ordering::Relaxed));
    }
}

"""+s
(r/'probe/src/eval.rs').write_text(s)
p=r/'probe/src/main.rs';s=p.read_text();assert s.count('    match out {\n')==1
p.write_text(s.replace('    match out {\n','    sokonanoda::eval::v79_report();\n    match out {\n',1))
PY
git clone -q --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
echo V79_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done
build(){ local a=$1; cd "$ROOT/$a"; RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q; cp target/release/sokonanoda "$ROOT/$a.bin"; }
build base; build probe
for c in std cedar mathlib; do
 "$ROOT/base.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$c.ndjson" > "$ROOT/out/base-$c.out"
 "$ROOT/probe.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$c.ndjson" > "$ROOT/out/probe-$c.out" 2> "$ROOT/$c.census"
 cmp "$ROOT/out/base-$c.out" "$ROOT/out/probe-$c.out"
 echo "V79_${c^^}_PROBE_REPLAY=EXACT"; cat "$ROOT/$c.census"
done
python3 - "$ROOT" <<'PY' | tee "$ROOT/summary.txt"
from pathlib import Path
import re,sys
r=Path(sys.argv[1]);text='\n'.join((r/(c+'.census')).read_text() for c in ['std','cedar','mathlib'])
active=[]
for i in range(4):
 hits=sum(map(int,re.findall(rf'V79_CELL_{i}_HITS=(\d+)',text)))
 ids=sum(map(int,re.findall(rf'V79_CELL_{i}_IDENTITY=(\d+)',text)))
 print(f'V79_CELL_{i}_TOTAL_HITS={hits}');print(f'V79_CELL_{i}_TOTAL_IDENTITY={ids}')
 if ids:active.append(i)
(r/'active.txt').write_text('\n'.join(map(str,active))+'\n' if active else '')
if not active:print('DECISION=NO_REACHABLE_IDENTITY_SHORTCUT__STOP_FACTORIAL__NO_CAUSAL_GAIN_ESTABLISHED')
else:print('DECISION=REACHABLE_RELATION__TEST_OBSERVED_CELLS')
PY
