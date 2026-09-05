#!/usr/bin/env bash
set -euxo pipefail

BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v60-incumbent /tmp/v60-arena /tmp/v60-hotspot-atlas
mkdir -p /tmp/v60-hotspot-atlas

git worktree add /tmp/v60-incumbent "$BASE"

# Reconstruct the verified semantic incumbent exactly: Pi fast path + relevance propagation-off.
python3 - <<'PY'
from pathlib import Path

p=Path('/tmp/v60-incumbent/src/eval.rs')
s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))

p=Path('/tmp/v60-incumbent/src/relevance.rs')
s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
assert s.count(old)==1
s=s.replace(old,'                let _ = r;',1)
p.write_text(s)
PY

cat >/tmp/v60-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}
EOF

# Reuse the previously successful deterministic profiling mechanism, but on the current incumbent.
git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v60-arena
cd /tmp/v60-arena
for t in init-prelude init std; do nix develop -c ./lka.py build-test "$t"; done

nix shell nixpkgs#llvmPackages_21.llvm -c llvm-profdata --version | tee /tmp/v60-hotspot-atlas/llvm-profdata-version.txt
nix shell nixpkgs#valgrind -c valgrind --version | tee /tmp/v60-hotspot-atlas/valgrind-version.txt

cd /tmp/v60-incumbent
rm -rf pgo && mkdir pgo
RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$PWD/pgo -C debuginfo=1" cargo build --release --locked
target/release/sokonanoda /tmp/v60-config.json < /tmp/v60-arena/_build/tests/init-prelude.ndjson >/dev/null
nix shell nixpkgs#llvmPackages_21.llvm -c llvm-profdata merge -o "$PWD/pgo/merged.profdata" "$PWD/pgo"
test -s "$PWD/pgo/merged.profdata"
RUSTFLAGS="-C target-cpu=native -Cprofile-use=$PWD/pgo/merged.profdata -C debuginfo=1" cargo build --release --locked
cp target/release/sokonanoda /tmp/v60-incumbent-bin

# Verify the profiling binary itself against the same incumbent built without debuginfo instrumentation.
RUSTFLAGS="-C target-cpu=native -Cprofile-use=$PWD/pgo/merged.profdata" cargo build --release --locked
cp target/release/sokonanoda /tmp/v60-replay-bin
for t in init std; do
  /tmp/v60-incumbent-bin /tmp/v60-config.json < "/tmp/v60-arena/_build/tests/$t.ndjson" >"/tmp/v60-$t-profile.out" 2>"/tmp/v60-$t-profile.err"
  /tmp/v60-replay-bin /tmp/v60-config.json < "/tmp/v60-arena/_build/tests/$t.ndjson" >"/tmp/v60-$t-replay.out" 2>"/tmp/v60-$t-replay.err"
  cmp "/tmp/v60-$t-profile.out" "/tmp/v60-$t-replay.out"
  echo "V60_${t^^}_SEMANTIC_REPLAY=EXACT"
done

profile_one() {
  local test="$1"
  local in="/tmp/v60-arena/_build/tests/$test.ndjson"
  local out="/tmp/v60-hotspot-atlas/$test.callgrind"
  echo "PROFILE_START $test" | tee -a /tmp/v60-hotspot-atlas/summary.txt
  /usr/bin/time -f "PROFILE_WALL_SECONDS=%e" -o "/tmp/v60-hotspot-atlas/$test.time" \
    nix shell nixpkgs#valgrind -c valgrind \
      --tool=callgrind --collect-jumps=yes --collect-systime=no \
      --callgrind-out-file="$out" \
      /tmp/v60-incumbent-bin /tmp/v60-config.json < "$in" >/dev/null 2>"/tmp/v60-hotspot-atlas/$test.stderr"
  cat "/tmp/v60-hotspot-atlas/$test.time" | tee -a /tmp/v60-hotspot-atlas/summary.txt
  nix shell nixpkgs#valgrind -c callgrind_annotate --inclusive=no --threshold=0.01 "$out" > "/tmp/v60-hotspot-atlas/$test.self.txt"
  nix shell nixpkgs#valgrind -c callgrind_annotate --inclusive=yes --threshold=0.01 "$out" > "/tmp/v60-hotspot-atlas/$test.inclusive.txt"
}

# One-thread profiling intentionally isolates semantic CPU work after the scheduling line was closed by v57.
profile_one init
profile_one std

python3 - <<'PY' | tee /tmp/v60-hotspot-atlas/decision.txt
from pathlib import Path
import re

root=Path('/tmp/v60-hotspot-atlas')

def parse(path):
    rows=[]
    text=Path(path).read_text(errors='ignore')
    rx=re.compile(r'^\s*([0-9,]+)\s+\(\s*([0-9.]+)%\)\s+(.+?)\s*$', re.M)
    for m in rx.finditer(text):
        n=int(m.group(1).replace(',',''))
        pct=float(m.group(2))
        label=m.group(3).strip()
        if label.startswith('PROGRAM TOTALS'):
            continue
        rows.append((pct,n,label))
    rows.sort(reverse=True)
    return rows

sets={}
for t in ('init','std'):
    rows=parse(root/f'{t}.self.txt')
    sets[t]={label:(pct,n) for pct,n,label in rows}
    print(f'=== V60_{t.upper()}_SELF_TOP ===')
    for pct,n,label in rows[:30]:
        print(f'{pct:7.3f}% {n:15,d} {label}')

common=set(sets['init']) & set(sets['std'])
rank=[]
for label in common:
    pi=sets['init'][label][0]
    ps=sets['std'][label][0]
    rank.append((min(pi,ps),(pi+ps)/2,pi,ps,label))
rank.sort(reverse=True)

print('=== V60_COMMON_SELF_HOTSPOTS ===')
for mn,av,pi,ps,label in rank[:40]:
    print(f'min={mn:6.3f}% avg={av:6.3f}% init={pi:6.3f}% std={ps:6.3f}% {label}')

if rank:
    mn,av,pi,ps,label=rank[0]
    print(f'V60_TOP_COMMON_TARGET={label}')
    print(f'V60_TOP_COMMON_MIN_SELF_SHARE={mn:.3f}%')
    print(f'V60_TOP_COMMON_AVG_SELF_SHARE={av:.3f}%')
    if mn >= 10.0:
        print('DECISION=V60_PHASE_CHANGE_COMMON_HOTSPOT__NEXT_CAUSAL_ABLATION_THIS_BASIN')
    elif mn >= 5.0:
        print('DECISION=V60_MATERIAL_COMMON_HOTSPOT__NEXT_CAUSAL_ABLATION_THIS_BASIN')
    else:
        print('DECISION=V60_NO_SINGLE_COMMON_SELF_HOTSPOT_GE_5PCT__READ_INCLUSIVE_PATHS_BEFORE_INTERVENTION')
else:
    print('DECISION=V60_NO_COMMON_SYMBOLS__READ_INCLUSIVE_PATHS_BEFORE_INTERVENTION')
print('RULE=PROFILE_CURRENT_INCUMBENT_FIRST__DO_NOT_REUSE_PRE_V51_HOTSPOT_CONCLUSIONS')
PY
