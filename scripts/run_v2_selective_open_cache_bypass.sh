#!/usr/bin/env bash
set -euxo pipefail

V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
rm -rf /tmp/arena-bypass /tmp/cache-bypass /tmp/{base,nolam,nolamlet,noapp}
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

cd "$GITHUB_WORKSPACE"
for arm in base nolam nolamlet noapp; do
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
 'nolamlet': '''            Expr::App { .. } | Expr::Proj { .. } | Expr::Pi { .. }\n''',
 'noapp': '''            Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }\n''',
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

# Semantic equality on all three real workloads before timing.
for t in init std mathlib; do
  f="/tmp/arena-bypass/_build/tests/$t.ndjson"
  timeout 900 /tmp/cache-bypass/base-checker /tmp/cache-bypass/checker.json < "$f" >"/tmp/cache-bypass/base-$t.out" 2>"/tmp/cache-bypass/base-$t.err"
  for arm in nolam nolamlet noapp; do
    timeout 900 "/tmp/cache-bypass/$arm-checker" /tmp/cache-bypass/checker.json < "$f" >"/tmp/cache-bypass/$arm-$t.out" 2>"/tmp/cache-bypass/$arm-$t.err"
    cmp "/tmp/cache-bypass/base-$t.out" "/tmp/cache-bypass/$arm-$t.out"
  done
done

printf 'test,arm,rep,instructions,seconds\n' >/tmp/cache-bypass/measurements.csv
for t in std mathlib; do
  f="/tmp/arena-bypass/_build/tests/$t.ndjson"
  for rep in 1 2; do
    if [ "$rep" = 1 ]; then arms='base nolam nolamlet noapp'; else arms='noapp nolamlet nolam base'; fi
    for arm in $arms; do
      pf="/tmp/cache-bypass/perf-$t-$arm-$rep.csv"
      tf="/tmp/cache-bypass/time-$t-$arm-$rep.txt"
      set +e
      /usr/bin/time -f '%e' -o "$tf" perf stat -x, -e instructions:u -o "$pf" "/tmp/cache-bypass/$arm-checker" /tmp/cache-bypass/checker.json < "$f" >/dev/null 2>"/tmp/cache-bypass/run-$t-$arm-$rep.err"
      st=$?
      set -e
      test "$st" -eq 0
      inst=$(awk -F, '$3=="instructions:u" || $3=="instructions" {gsub(/ /,"",$1); if ($1 !~ /not/) {print $1; exit}}' "$pf")
      sec=$(cat "$tf")
      test -n "$inst"
      test -n "$sec"
      printf '%s,%s,%s,%s,%s\n' "$t" "$arm" "$rep" "$inst" "$sec" >>/tmp/cache-bypass/measurements.csv
    done
  done
done

python3 - <<'PY' | tee /tmp/cache-bypass/summary.txt
import csv, statistics
rows=list(csv.DictReader(open('/tmp/cache-bypass/measurements.csv')))
arms=['base','nolam','nolamlet','noapp']
def vals(t,a,k):
    typ=int if k=='instructions' else float
    return [typ(r[k]) for r in rows if r['test']==t and r['arm']==a]
def med(t,a,k): return statistics.median(vals(t,a,k))
for t in ['std','mathlib']:
    print('\nTEST',t)
    bi=med(t,'base','instructions'); bw=med(t,'base','seconds')
    print('base', 'instructions',bi,'seconds',bw)
    for a in arms[1:]:
        i=med(t,a,'instructions'); w=med(t,a,'seconds')
        print(a,'instructions',i,f'ir_ratio={i/bi:.6f}',f'ir_delta={(i/bi-1)*100:+.3f}%',
              'seconds',w,f'wall_ratio={w/bw:.6f}',f'wall_delta={(w/bw-1)*100:+.3f}%')

# Promotion must improve deterministic instruction count on both workloads.
qualified=[]
for a in arms[1:]:
    qs=med('std',a,'instructions')/med('std','base','instructions')
    qm=med('mathlib',a,'instructions')/med('mathlib','base','instructions')
    if qs < 1 and qm < 1:
        qualified.append((qm,a,qs))
if not qualified:
    print('\nDECISION=REJECT_SIMPLE_CLASS_BYPASS__OPTIMIZE_PRUNE_RECONSTRUCTION')
else:
    qm,a,qs=min(qualified)
    print('\nBEST='+a)
    print('BEST_STD_RATIO='+f'{qs:.6f}')
    print('BEST_MATHLIB_RATIO='+f'{qm:.6f}')
    if qm <= .90 and qs <= .95:
        d='PHASE_CHANGE_CACHE_BYPASS__FULL_ARENA_GATE_NOW'
    elif qm <= .95:
        d='MAJOR_CACHE_BYPASS_GAIN__FULL_ARENA_GATE_NOW'
    elif qm <= .98:
        d='MATERIAL_CACHE_BYPASS_GAIN__EXPAND_SELECTIVE_POLICY'
    else:
        d='SMALL_CACHE_BYPASS_GAIN__DO_NOT_OVERFIT'
    print('DECISION='+d)
PY
