#!/usr/bin/env bash
set -euo pipefail

V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
rm -rf /tmp/v2-hot /tmp/arena-hot /tmp/hotspot-atlas
mkdir -p /tmp/hotspot-atlas

git worktree add /tmp/v2-hot "$V2"
cd /tmp/v2-hot

# Build the scored substrate with Arena-style init-prelude PGO, adding only debug info
# so Callgrind can attribute optimized instructions to functions.
cat > /tmp/hotspot-checker.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/arena-hot
cd /tmp/arena-hot
nix develop -c ./lka.py build-test init-prelude
nix develop -c ./lka.py build-test init
nix develop -c ./lka.py build-test std

# Fail early on the profiling toolchain boundary rather than after generating PGO data.
# The runner image does not guarantee llvm-profdata on PATH, so use Nix explicitly.
nix shell nixpkgs#llvmPackages_21.llvm -c llvm-profdata --version | tee /tmp/hotspot-atlas/llvm-profdata-version.txt
nix shell nixpkgs#valgrind -c valgrind --version | tee /tmp/hotspot-atlas/valgrind-version.txt

cd /tmp/v2-hot
rm -rf pgo && mkdir pgo
RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$PWD/pgo -C debuginfo=1" cargo build --release --locked
target/release/sokonanoda /tmp/hotspot-checker.json < /tmp/arena-hot/_build/tests/init-prelude.ndjson >/dev/null
nix shell nixpkgs#llvmPackages_21.llvm -c llvm-profdata merge -o "$PWD/pgo/merged.profdata" "$PWD/pgo"
test -s "$PWD/pgo/merged.profdata"
RUSTFLAGS="-C target-cpu=native -Cprofile-use=$PWD/pgo/merged.profdata -C debuginfo=1" cargo build --release --locked
cp target/release/sokonanoda /tmp/v2-hotspot-checker

profile_one() {
  local test="$1"
  local slug="${test//\//-}"
  local in="/tmp/arena-hot/_build/tests/$test.ndjson"
  local out="/tmp/hotspot-atlas/$slug.callgrind"
  echo "PROFILE_START $test" | tee -a /tmp/hotspot-atlas/summary.txt
  /usr/bin/time -f "PROFILE_WALL_SECONDS=%e" -o "/tmp/hotspot-atlas/$slug.time" \
    nix shell nixpkgs#valgrind -c valgrind \
      --tool=callgrind --collect-jumps=yes --collect-systime=no \
      --callgrind-out-file="$out" \
      /tmp/v2-hotspot-checker /tmp/hotspot-checker.json < "$in" >/dev/null 2>"/tmp/hotspot-atlas/$slug.stderr"
  cat "/tmp/hotspot-atlas/$slug.time" | tee -a /tmp/hotspot-atlas/summary.txt
  nix shell nixpkgs#valgrind -c callgrind_annotate --inclusive=no --threshold=0.01 "$out" > "/tmp/hotspot-atlas/$slug.self.txt"
  nix shell nixpkgs#valgrind -c callgrind_annotate --inclusive=yes --threshold=0.01 "$out" > "/tmp/hotspot-atlas/$slug.inclusive.txt"
}

# init is a substantial real Lean library workload; std adds a second, larger real corpus.
profile_one init
profile_one std

python3 - <<'PY' | tee /tmp/hotspot-atlas/decision.txt
from pathlib import Path
import re

root=Path('/tmp/hotspot-atlas')

def parse_annotate(path):
    rows=[]
    text=Path(path).read_text(errors='ignore')
    # Typical callgrind_annotate row: 12,345,678 (12.34%) file:function
    rx=re.compile(r'^\s*([0-9,]+)\s+\(\s*([0-9.]+)%\)\s+(.+?)\s*$', re.M)
    for m in rx.finditer(text):
        n=int(m.group(1).replace(',',''))
        pct=float(m.group(2))
        label=m.group(3).strip()
        # Skip annotation headers/source lines that happen to match.
        if label.startswith('PROGRAM TOTALS'):
            continue
        rows.append((pct,n,label))
    rows.sort(reverse=True)
    return rows

for slug in ('init','std'):
    print(f'\n=== {slug.upper()} SELF ===')
    self_rows=parse_annotate(root/f'{slug}.self.txt')
    for pct,n,label in self_rows[:40]:
        print(f'{pct:7.3f}% {n:15,d} {label}')
    print(f'\n=== {slug.upper()} INCLUSIVE ===')
    inc_rows=parse_annotate(root/f'{slug}.inclusive.txt')
    for pct,n,label in inc_rows[:40]:
        print(f'{pct:7.3f}% {n:15,d} {label}')

# Cross-workload common-hot ranking: minimum self share across init and std.
sets={}
for slug in ('init','std'):
    d={label:(pct,n) for pct,n,label in parse_annotate(root/f'{slug}.self.txt')}
    sets[slug]=d
common=set(sets['init']) & set(sets['std'])
rank=[]
for label in common:
    pi=sets['init'][label][0]; ps=sets['std'][label][0]
    rank.append((min(pi,ps), (pi+ps)/2, pi, ps, label))
rank.sort(reverse=True)
print('\n=== COMMON SELF HOTSPOTS (ranked by min share) ===')
for mn,av,pi,ps,label in rank[:50]:
    print(f'min={mn:6.3f}% avg={av:6.3f}% init={pi:6.3f}% std={ps:6.3f}% {label}')

major=[r for r in rank if r[0] >= 5.0]
phase=[r for r in rank if r[0] >= 10.0]
print('\n=== ROUTE ===')
if phase:
    print('DECISION=PHASE_CHANGE_COMMON_HOTSPOT')
    print('TARGET='+phase[0][4])
    print(f'MIN_SELF_SHARE={phase[0][0]:.3f}%')
elif major:
    print('DECISION=MATERIAL_COMMON_HOTSPOT')
    print('TARGET='+major[0][4])
    print(f'MIN_SELF_SHARE={major[0][0]:.3f}%')
else:
    print('DECISION=NO_SINGLE_COMMON_SELF_HOTSPOT_GE_5_PERCENT')
    print('NEXT=inspect inclusive common paths and allocation/hash-cons families before intervention')
PY

cp /tmp/hotspot-atlas/summary.txt /tmp/hotspot-atlas/README.txt
