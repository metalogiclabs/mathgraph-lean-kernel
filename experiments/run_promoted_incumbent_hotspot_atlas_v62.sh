#!/usr/bin/env bash
set -euxo pipefail

SOKO=7b51784fe4ec9b82bf7a20c71ba6bf803a4ed7c0
ROOT=/tmp/v62
rm -rf "$ROOT"
mkdir -p "$ROOT/atlas"

git clone https://github.com/intgrah/sokonanoda "$ROOT/incumbent"
git -C "$ROOT/incumbent" checkout "$SOKO"

python3 - "$ROOT/incumbent" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/'src/eval.rs'
s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
p=root/'src/relevance.rs'
s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
assert s.count(old)==1
p.write_text(s.replace(old,'                let _ = r;',1))
PY

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" rev-parse HEAD | tee "$ROOT/atlas/arena-head.txt"
cd "$ROOT/arena"
for t in init-prelude init std; do nix develop -c ./lka.py build-test "$t"; done

cd "$ROOT/incumbent"
rm -rf pgo target
mkdir pgo
RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$PWD/pgo -C debuginfo=1" cargo build --release --locked
./target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/init-prelude.ndjson" >/dev/null
nix shell nixpkgs#llvmPackages_21.llvm -c llvm-profdata merge -o "$PWD/pgo/merged.profdata" "$PWD/pgo"
test -s "$PWD/pgo/merged.profdata"
rm -rf target
RUSTFLAGS="-C target-cpu=native -Cprofile-use=$PWD/pgo/merged.profdata -C debuginfo=1" cargo build --release --locked
cp target/release/sokonanoda "$ROOT/profile.bin"
rm -rf target
RUSTFLAGS="-C target-cpu=native -Cprofile-use=$PWD/pgo/merged.profdata" cargo build --release --locked
cp target/release/sokonanoda "$ROOT/replay.bin"

for t in init std; do
  "$ROOT/profile.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" >"$ROOT/$t-profile.out" 2>"$ROOT/$t-profile.err"
  "$ROOT/replay.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" >"$ROOT/$t-replay.out" 2>"$ROOT/$t-replay.err"
  cmp "$ROOT/$t-profile.out" "$ROOT/$t-replay.out"
  echo "V62_${t^^}_SEMANTIC_REPLAY=EXACT"
done

profile_one() {
  local t="$1"
  /usr/bin/time -f '%e' -o "$ROOT/atlas/$t.wall" \
    nix shell nixpkgs#valgrind -c valgrind --tool=callgrind --collect-jumps=yes --collect-systime=no \
      --callgrind-out-file="$ROOT/atlas/$t.callgrind" \
      "$ROOT/profile.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" >/dev/null 2>"$ROOT/atlas/$t.stderr"
  nix shell nixpkgs#valgrind -c callgrind_annotate --inclusive=no --threshold=0.01 "$ROOT/atlas/$t.callgrind" > "$ROOT/atlas/$t.self.txt"
  nix shell nixpkgs#valgrind -c callgrind_annotate --inclusive=yes --threshold=0.01 "$ROOT/atlas/$t.callgrind" > "$ROOT/atlas/$t.inclusive.txt"
}
profile_one init
profile_one std

python3 - <<'PY' | tee "$ROOT/atlas/decision.txt"
from pathlib import Path
import re
root=Path('/tmp/v62/atlas')
rx=re.compile(r'^\s*([0-9,]+)\s+\(\s*([0-9.]+)%\)\s+(.+?)\s*$', re.M)
def parse(p):
    rows=[]
    for m in rx.finditer(Path(p).read_text(errors='ignore')):
        n=int(m.group(1).replace(',','')); pct=float(m.group(2)); label=m.group(3).strip()
        if not label.startswith('PROGRAM TOTALS'): rows.append((pct,n,label))
    return sorted(rows, reverse=True)
sets={}
for t in ('init','std'):
    rows=parse(root/f'{t}.self.txt')
    sets[t]={label:(pct,n) for pct,n,label in rows}
    print(f'=== V62_{t.upper()}_SELF_TOP ===')
    for pct,n,label in rows[:40]: print(f'{pct:7.3f}% {n:15,d} {label}')
common=set(sets['init']) & set(sets['std'])
rank=[]
for label in common:
    pi=sets['init'][label][0]; ps=sets['std'][label][0]
    rank.append((min(pi,ps),(pi+ps)/2,pi,ps,label))
rank.sort(reverse=True)
print('=== V62_COMMON_SELF_HOTSPOTS ===')
for mn,av,pi,ps,label in rank[:50]: print(f'min={mn:6.3f}% avg={av:6.3f}% init={pi:6.3f}% std={ps:6.3f}% {label}')
if rank:
    mn,av,pi,ps,label=rank[0]
    print(f'V62_TOP_COMMON_TARGET={label}')
    print(f'V62_TOP_COMMON_MIN_SELF_SHARE={mn:.3f}%')
    print(f'V62_TOP_COMMON_AVG_SELF_SHARE={av:.3f}%')
    if mn >= 10: print('DECISION=V62_PHASE_CHANGE_BASIN__DECOMPOSE_AND_TEST_EARLY_SEMANTIC_BYPASS')
    elif mn >= 5: print('DECISION=V62_MATERIAL_BASIN__DECOMPOSE_AND_TEST_EARLY_SEMANTIC_BYPASS')
    else: print('DECISION=V62_NO_SINGLE_COMMON_SELF_HOTSPOT_GE_5PCT__READ_INCLUSIVE_PATHS')
else: print('DECISION=V62_NO_COMMON_SYMBOLS__READ_INCLUSIVE_PATHS')
print('RULE=PROFILE_PROMOTED_INCUMBENT__DELETE_WORK_BEFORE_MAKING_WORK_CHEAPER')
PY
