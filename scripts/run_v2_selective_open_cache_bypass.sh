#!/usr/bin/env bash
set -euxo pipefail

V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
rm -rf /tmp/arena-bypass /tmp/cache-bypass /tmp/{base,nolam,nolet,nolamlet}
mkdir -p /tmp/cache-bypass

cat >/tmp/cache-bypass/checker.json <<'EOF'
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

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/arena-bypass
cd /tmp/arena-bypass
for t in init-prelude init std mathlib; do
  nix develop -c ./lka.py build-test "$t"
done
PROFDATA=$(nix develop -c bash -lc 'command -v llvm-profdata')
test -x "$PROFDATA"
# Arena's dev shell does not include valgrind. Resolve it explicitly through
# nixpkgs so hosted runners do not depend on ambient packages/PATH.
nix shell nixpkgs#valgrind --command valgrind --version

cd "$GITHUB_WORKSPACE"
for arm in base nolam nolet nolamlet; do
  git worktree add "/tmp/$arm" "$V2"
  if [ "$arm" != base ]; then
    python3 - "$arm" <<'PY'
from pathlib import Path
import sys
arm=sys.argv[1]
p=Path('/tmp')/arm/'src/eval.rs'
s=p.read_text()
old='''            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }\n'''
repls={
 'nolam': '''            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. }\n''',
 'nolet': '''            Expr::App { .. } | Expr::Proj { .. } | Expr::Pi { .. } | Expr::Lambda { .. }\n''',
 'nolamlet': '''            Expr::App { .. } | Expr::Proj { .. } | Expr::Pi { .. }\n''',
}
assert old in s, 'open-eval eligibility anchor not found'
p.write_text(s.replace(old,repls[arm],1))
PY
  fi
  cd "/tmp/$arm"
  cargo test --release --locked
  rm -rf pgo target
  RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$PWD/pgo" cargo build --release --locked
  target/release/sokonanoda /tmp/cache-bypass/checker.json < /tmp/arena-bypass/_build/tests/init-prelude.ndjson >/dev/null
  "$PROFDATA" merge -o "$PWD/pgo/merged.profdata" "$PWD/pgo"
  RUSTFLAGS="-C target-cpu=native -Cprofile-use=$PWD/pgo/merged.profdata" cargo build --release --locked
  cp target/release/sokonanoda "/tmp/cache-bypass/$arm-checker"
done

# Semantic equality on all three real workloads before measurement.
for t in init std mathlib; do
  f="/tmp/arena-bypass/_build/tests/$t.ndjson"
  timeout 900 /tmp/cache-bypass/base-checker /tmp/cache-bypass/checker.json < "$f" >"/tmp/cache-bypass/base-$t.out" 2>"/tmp/cache-bypass/base-$t.err"
  for arm in nolam nolet nolamlet; do
    timeout 900 "/tmp/cache-bypass/$arm-checker" /tmp/cache-bypass/checker.json < "$f" >"/tmp/cache-bypass/$arm-$t.out" 2>"/tmp/cache-bypass/$arm-$t.err"
    cmp "/tmp/cache-bypass/base-$t.out" "/tmp/cache-bypass/$arm-$t.out"
  done
done

# GitHub-hosted perf_event is unavailable. Use Callgrind Ir for deterministic
# instruction attribution on the two smaller real workloads, then paired wall
# time on full Mathlib. Valgrind is invoked through nixpkgs explicitly.
printf 'test,arm,instructions\n' >/tmp/cache-bypass/callgrind.csv
for t in init std; do
  f="/tmp/arena-bypass/_build/tests/$t.ndjson"
  for arm in base nolam nolet nolamlet; do
    cf="/tmp/cache-bypass/callgrind-$t-$arm.out"
    timeout 1200 nix shell nixpkgs#valgrind --command valgrind \
      --tool=callgrind --callgrind-out-file="$cf" \
      "/tmp/cache-bypass/$arm-checker" /tmp/cache-bypass/checker.json < "$f" >/dev/null \
      2>"/tmp/cache-bypass/callgrind-$t-$arm.err"
    inst=$(awk '/^summary:/ {print $2; exit}' "$cf")
    test -n "$inst"
    printf '%s,%s,%s\n' "$t" "$arm" "$inst" >>/tmp/cache-bypass/callgrind.csv
  done
done

printf 'test,arm,rep,seconds\n' >/tmp/cache-bypass/wall.csv
f=/tmp/arena-bypass/_build/tests/mathlib.ndjson
for rep in 1 2; do
  if [ "$rep" = 1 ]; then arms='base nolam nolet nolamlet'; else arms='nolamlet nolet nolam base'; fi
  for arm in $arms; do
    tf="/tmp/cache-bypass/time-mathlib-$arm-$rep.txt"
    timeout 900 /usr/bin/time -f '%e' -o "$tf" "/tmp/cache-bypass/$arm-checker" \
      /tmp/cache-bypass/checker.json < "$f" >/dev/null \
      2>"/tmp/cache-bypass/run-mathlib-$arm-$rep.err"
    sec=$(cat "$tf")
    test -n "$sec"
    printf 'mathlib,%s,%s,%s\n' "$arm" "$rep" "$sec" >>/tmp/cache-bypass/wall.csv
  done
done

python3 - <<'PY' | tee /tmp/cache-bypass/summary.txt
import csv, statistics
ir=list(csv.DictReader(open('/tmp/cache-bypass/callgrind.csv')))
wall=list(csv.DictReader(open('/tmp/cache-bypass/wall.csv')))
arms=['base','nolam','nolet','nolamlet']
def I(t,a): return int(next(r['instructions'] for r in ir if r['test']==t and r['arm']==a))
def W(a): return statistics.median(float(r['seconds']) for r in wall if r['arm']==a)
for t in ['init','std']:
    b=I(t,'base')
    print('\nTEST',t,'CALLGRIND_IR')
    print('base',b)
    for a in arms[1:]:
        x=I(t,a); q=x/b
        print(a,x,f'ratio={q:.6f}',f'delta={(q-1)*100:+.3f}%')
print('\nTEST mathlib WALL_SECONDS')
b=W('base'); print('base',b)
for a in arms[1:]:
    x=W(a); q=x/b
    print(a,x,f'ratio={q:.6f}',f'delta={(q-1)*100:+.3f}%')

qualified=[]
for a in arms[1:]:
    qi=I('init',a)/I('init','base')
    qs=I('std',a)/I('std','base')
    qw=W(a)/W('base')
    if qi < 1 and qs < 1 and qw < 1:
        qualified.append((qs,a,qi,qw))
if not qualified:
    print('\nDECISION=REJECT_LAMBDA_LET_BYPASS__OPTIMIZE_PRUNE_RECONSTRUCTION')
else:
    qs,a,qi,qw=min(qualified)
    print('\nBEST='+a)
    print('BEST_INIT_IR_RATIO='+f'{qi:.6f}')
    print('BEST_STD_IR_RATIO='+f'{qs:.6f}')
    print('BEST_MATHLIB_WALL_RATIO='+f'{qw:.6f}')
    if qs <= .90 and qi <= .95 and qw <= .95:
        d='PHASE_CHANGE_CACHE_BYPASS__FULL_ARENA_GATE_NOW'
    elif qs <= .95 and qw <= .97:
        d='MAJOR_CACHE_BYPASS_GAIN__FULL_ARENA_GATE_NOW'
    elif qs <= .98:
        d='MATERIAL_CACHE_BYPASS_GAIN__EXPAND_SELECTIVE_POLICY'
    else:
        d='SMALL_CACHE_BYPASS_GAIN__DO_NOT_OVERFIT'
    print('DECISION='+d)
PY
