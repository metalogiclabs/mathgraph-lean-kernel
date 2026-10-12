#!/usr/bin/env bash
set -euo pipefail

V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
rm -rf /tmp/v2-lines /tmp/arena-lines /tmp/eval-line-atlas
mkdir -p /tmp/eval-line-atlas

git worktree add /tmp/v2-lines "$V2"
cd /tmp/v2-lines
cat > /tmp/eval-line-checker.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/arena-lines
cd /tmp/arena-lines
nix develop -c ./lka.py build-test init-prelude
nix develop -c ./lka.py build-test init
nix develop -c ./lka.py build-test std

# Pin profiling tools explicitly; fail before the expensive build if unavailable.
nix shell nixpkgs#llvmPackages_21.llvm -c llvm-profdata --version | tee /tmp/eval-line-atlas/llvm-profdata-version.txt
nix shell nixpkgs#valgrind -c valgrind --version | tee /tmp/eval-line-atlas/valgrind-version.txt

cd /tmp/v2-lines
rm -rf pgo && mkdir pgo
RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$PWD/pgo -C debuginfo=2" cargo build --release --locked
target/release/sokonanoda /tmp/eval-line-checker.json < /tmp/arena-lines/_build/tests/init-prelude.ndjson >/dev/null
nix shell nixpkgs#llvmPackages_21.llvm -c llvm-profdata merge -o "$PWD/pgo/merged.profdata" "$PWD/pgo"
test -s "$PWD/pgo/merged.profdata"
RUSTFLAGS="-C target-cpu=native -Cprofile-use=$PWD/pgo/merged.profdata -C debuginfo=2" cargo build --release --locked
cp target/release/sokonanoda /tmp/v2-eval-line-checker

profile_one() {
  local test="$1"
  local in="/tmp/arena-lines/_build/tests/$test.ndjson"
  local out="/tmp/eval-line-atlas/$test.callgrind"
  echo "PROFILE_START $test" | tee -a /tmp/eval-line-atlas/summary.txt
  /usr/bin/time -f "PROFILE_WALL_SECONDS=%e" -o "/tmp/eval-line-atlas/$test.time" \
    nix shell nixpkgs#valgrind -c valgrind \
      --tool=callgrind --collect-jumps=yes --collect-systime=no \
      --callgrind-out-file="$out" \
      /tmp/v2-eval-line-checker /tmp/eval-line-checker.json < "$in" >/dev/null 2>"/tmp/eval-line-atlas/$test.stderr"
  cat "/tmp/eval-line-atlas/$test.time" | tee -a /tmp/eval-line-atlas/summary.txt
  # Source-aware annotation. Keeping the V2 worktree alive lets callgrind_annotate resolve eval.rs.
  (cd /tmp/v2-lines && nix shell nixpkgs#valgrind -c callgrind_annotate \
      --auto=yes --inclusive=no --threshold=0.00 --show=Ir "$out") \
      > "/tmp/eval-line-atlas/$test.source.txt"
}

profile_one init
profile_one std

python3 - <<'PY' | tee /tmp/eval-line-atlas/decision.txt
from pathlib import Path
import re
root=Path('/tmp/eval-line-atlas')

# Extract source annotation lines inside src/eval.rs, ranked by instruction count.
# callgrind_annotate source rows begin with an Ir count followed by source text.
def extract(test):
    text=(root/f'{test}.source.txt').read_text(errors='ignore').splitlines()
    in_eval=False
    rows=[]
    for line in text:
        if 'src/eval.rs' in line:
            in_eval=True
            continue
        if in_eval and line.startswith('---'):
            continue
        if in_eval and line.startswith('The following files chosen for auto-annotation'):
            break
        if in_eval:
            m=re.match(r'^\s*([0-9,]+)\s+(.*)$', line)
            if m:
                n=int(m.group(1).replace(',',''))
                src=m.group(2).rstrip()
                if n:
                    rows.append((n,src))
    return rows

sets={}
for test in ('init','std'):
    rows=extract(test)
    sets[test]=rows
    print(f'=== {test.upper()} EVAL.RS HOT SOURCE LINES ===')
    for n,src in sorted(rows, reverse=True)[:40]:
        print(f'{n:15,d} {src}')
    print()

# Normalize by total instructions from callgrind event summary.
def total(test):
    txt=(root/f'{test}.callgrind').read_text(errors='ignore')
    m=re.search(r'^summary:\s*(\d+)',txt,re.M)
    return int(m.group(1)) if m else 0

for test in ('init','std'):
    t=total(test)
    top=sum(n for n,_ in sorted(sets[test], reverse=True)[:10])
    print(f'{test.upper()}_TOTAL_IR={t}')
    print(f'{test.upper()}_TOP10_EVAL_SOURCE_IR={top}')
    if t:
        print(f'{test.upper()}_TOP10_EVAL_SOURCE_SHARE={100*top/t:.3f}%')

print('DECISION=USE_SOURCE_LINE_ATTRIBUTION_TO_SELECT_NEXT_CAUSAL_EVAL_A_B')
PY
