#!/usr/bin/env bash
set -euxo pipefail

V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
rm -rf /tmp/arena /tmp/base /tmp/dm16k /tmp/dm64k /tmp/dm256k
cat >/tmp/checker.json <<'EOF'
{
  "use_stdin": true,
  "nat_extension": true,
  "string_extension": true,
  "unpermitted_axiom_hard_error": false,
  "unsafe_permit_all_axioms": true,
  "num_threads": 4,
  "print_success_message": false
}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/arena
cd /tmp/arena
for t in init-prelude std mathlib; do nix develop -c ./lka.py build-test "$t"; done

cd "$GITHUB_WORKSPACE"
for spec in base:10 dm16k:14 dm64k:16 dm256k:18; do
  arm=${spec%%:*}; bits=${spec##*:}
  git worktree add "/tmp/$arm" "$V2"
  if [ "$arm" != base ]; then
    python3 - "$arm" "$bits" <<'PY'
from pathlib import Path
import sys
arm,bits=sys.argv[1],int(sys.argv[2])
p=Path('/tmp')/arm/'src/util.rs'
s=p.read_text()
old='pub(crate) const PRUNE_DM_LEN: usize = 1 << 10;\npub(crate) const PRUNE_DM_SHIFT: u32 = 64 - 10;'
new=f'pub(crate) const PRUNE_DM_LEN: usize = 1 << {bits};\npub(crate) const PRUNE_DM_SHIFT: u32 = 64 - {bits};'
assert old in s
p.write_text(s.replace(old,new,1))
PY
  fi
  cd "/tmp/$arm"
  cargo test --release --locked
  rm -rf pgo target
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$PWD/pgo" cargo build --release --locked
  target/release/sokonanoda /tmp/checker.json < /tmp/arena/_build/tests/init-prelude.ndjson >/dev/null
  llvm-profdata merge -o "$PWD/pgo/merged.profdata" "$PWD/pgo"
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=$PWD/pgo/merged.profdata" cargo build --release --locked
  cp target/release/sokonanoda "/tmp/$arm-checker"
done

for t in std mathlib; do
  for arm in base dm16k dm64k dm256k; do
    timeout 600 "/tmp/$arm-checker" /tmp/checker.json < "/tmp/arena/_build/tests/$t.ndjson" >/tmp/${arm}-${t}.out 2>/tmp/${arm}-${t}.err
  done
done

printf 'test,arm,rep,instructions\n' >/tmp/instructions.csv
for t in std mathlib; do
  file="/tmp/arena/_build/tests/$t.ndjson"
  for rep in 1 2; do
    if [ "$rep" = 1 ]; then arms='base dm16k dm64k dm256k'; else arms='dm256k dm64k dm16k base'; fi
    for arm in $arms; do
      out="/tmp/perf-${t}-${arm}-${rep}.txt"
      perf stat -x, -e instructions:u -o "$out" "/tmp/$arm-checker" /tmp/checker.json < "$file" >/dev/null 2>/tmp/${t}-${arm}-${rep}.err
      inst=$(awk -F, '$3=="instructions:u" || $3=="instructions" {gsub(/ /,"",$1); print $1; exit}' "$out")
      test -n "$inst"
      printf '%s,%s,%s,%s\n' "$t" "$arm" "$rep" "$inst" >>/tmp/instructions.csv
    done
  done
done

python3 - <<'PY' | tee /tmp/summary.txt
import csv, statistics
rows=list(csv.DictReader(open('/tmp/instructions.csv')))
def med(t,a): return statistics.median(int(r['instructions']) for r in rows if r['test']==t and r['arm']==a)
arms=['base','dm16k','dm64k','dm256k']
for t in ['std','mathlib']:
    b=med(t,'base')
    print(t,'base',b)
    for a in arms[1:]:
        x=med(t,a); q=x/b
        print(t,a,x,f'ratio={q:.6f}',f'delta={(q-1)*100:+.3f}%')
best=min(arms,key=lambda a: med('mathlib',a))
q=med('mathlib',best)/med('mathlib','base')
if best!='base' and q <= .90:
    d='CAPACITY_COLLISION_PHASE_CHANGE__PROMOTE_AND_TEST_FULL_ARENA'
elif best!='base' and q <= .97:
    d='CAPACITY_MATTERS__BUILD_SET_ASSOCIATIVE_OR_EXACT_ENV_MASK_CACHE'
else:
    d='CAPACITY_FLAT__COLD_MISSES_ARE_STRUCTURAL__CARRY_CANONICAL_ENV_IDENTITY_FORWARD'
print('BEST='+best)
print('BEST_MATHLIB_RATIO=',f'{q:.6f}')
print('DECISION='+d)
PY
