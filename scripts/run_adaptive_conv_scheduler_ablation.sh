#!/usr/bin/env bash
set -euxo pipefail
V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
ROOT=$(pwd)
rm -rf /tmp/mg-ablate-* /tmp/arena-adapt

for arm in baseline left right shorter; do
  git worktree add "/tmp/mg-ablate-$arm" "$V2"
done

python3 - <<'PY'
from pathlib import Path

old = '''                    } else {
                        self.unfold_pair(depth, t, t2)
                    }
'''

left = '''                    } else {
                        // Equal reducibility hints: avoid eagerly reducing both sides.
                        // Try one legal distinction-changing step on the left first.
                        let v1 = self.unfold_value(depth, t);
                        if !std::ptr::eq(v1, t) {
                            return self.unify::<true>(depth, v1, t2);
                        }
                        let v2 = self.unfold_value(depth, t2);
                        if !std::ptr::eq(v2, t2) {
                            return self.unify::<true>(depth, t, v2);
                        }
                        let f1 = self.unfold_value_demand(depth, t);
                        if !std::ptr::eq(f1, t) {
                            return self.unify::<true>(depth, f1, t2);
                        }
                        let f2 = self.unfold_value_demand(depth, t2);
                        if !std::ptr::eq(f2, t2) {
                            return self.unify::<true>(depth, t, f2);
                        }
                        false
                    }
'''

right = '''                    } else {
                        // Equal reducibility hints: avoid eagerly reducing both sides.
                        // Symmetric ablation: try the right side first.
                        let v2 = self.unfold_value(depth, t2);
                        if !std::ptr::eq(v2, t2) {
                            return self.unify::<true>(depth, t, v2);
                        }
                        let v1 = self.unfold_value(depth, t);
                        if !std::ptr::eq(v1, t) {
                            return self.unify::<true>(depth, v1, t2);
                        }
                        let f2 = self.unfold_value_demand(depth, t2);
                        if !std::ptr::eq(f2, t2) {
                            return self.unify::<true>(depth, t, f2);
                        }
                        let f1 = self.unfold_value_demand(depth, t);
                        if !std::ptr::eq(f1, t) {
                            return self.unify::<true>(depth, f1, t2);
                        }
                        false
                    }
'''

shorter = '''                    } else {
                        // Equal reducibility hints: schedule the cheaper-looking side first.
                        // Spine length is already available and costs no semantic work to inspect.
                        if sx.len() <= sy.len() {
                            let v1 = self.unfold_value(depth, t);
                            if !std::ptr::eq(v1, t) {
                                return self.unify::<true>(depth, v1, t2);
                            }
                            let v2 = self.unfold_value(depth, t2);
                            if !std::ptr::eq(v2, t2) {
                                return self.unify::<true>(depth, t, v2);
                            }
                        } else {
                            let v2 = self.unfold_value(depth, t2);
                            if !std::ptr::eq(v2, t2) {
                                return self.unify::<true>(depth, t, v2);
                            }
                            let v1 = self.unfold_value(depth, t);
                            if !std::ptr::eq(v1, t) {
                                return self.unify::<true>(depth, v1, t2);
                            }
                        }
                        self.unfold_pair(depth, t, t2)
                    }
'''

for arm, repl in [('left',left),('right',right),('shorter',shorter)]:
    p=Path(f'/tmp/mg-ablate-{arm}/src/conv.rs')
    s=p.read_text()
    # Patch only the equal-hint branch in the mismatched Unfold/Unfold case.
    anchor='''                    } else if rh.is_lt(&lh) {'''
    pos=s.index(anchor)
    target=s.index(old,pos)
    s=s[:target]+s[target:].replace(old,repl,1)
    p.write_text(s)
PY

for arm in baseline left right shorter; do
  cd "/tmp/mg-ablate-$arm"
  cargo test --release --locked
  RUSTFLAGS='-C target-cpu=x86-64' cargo build --release --locked
  cp target/release/sokonanoda "/tmp/mg-$arm"
done

cat >/tmp/checker.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/arena-adapt
cd /tmp/arena-adapt
# Build diagnostic cases that isolate conversion scheduling plus full Mathlib.
for t in perf/unroll-versus-evaluate perf/discarded-argument perf/identical-nesting perf/repeated-subproblem perf/refute-cheap-first perf/refute-cheap-last mathlib; do
  nix develop -c ./lka.py build-test "$t"
done

: > /tmp/adaptive-times.tsv
measure () {
  local arm=$1 test=$2 rep=$3
  local out err tm
  out="/tmp/${arm}-${test//\//_}-${rep}.out"
  err="/tmp/${arm}-${test//\//_}-${rep}.err"
  tm=$(/usr/bin/time -f '%e' -o /tmp/time.txt "/tmp/mg-$arm" /tmp/checker.json < "_build/tests/$test.ndjson" >"$out" 2>"$err"; cat /tmp/time.txt)
  printf '%s\t%s\t%s\t%s\n' "$arm" "$test" "$rep" "$tm" >> /tmp/adaptive-times.tsv
}

# Diagnostics: enough repetitions to reveal directional wins without spending Mathlib budget yet.
for test in perf/unroll-versus-evaluate perf/discarded-argument perf/identical-nesting perf/repeated-subproblem perf/refute-cheap-first perf/refute-cheap-last; do
  for rep in 1 2 3 4 5; do
    for arm in baseline left right shorter; do measure "$arm" "$test" "$rep"; done
  done
done

# Full Mathlib: alternating order, three reps each.
orders=("baseline left right shorter" "shorter right left baseline" "right baseline shorter left")
rep=0
for order in "${orders[@]}"; do
  rep=$((rep+1))
  for arm in $order; do measure "$arm" mathlib "$rep"; done
done

python3 - <<'PY' | tee /tmp/adaptive-decision.txt
import csv, statistics
from collections import defaultdict
rows=defaultdict(list)
with open('/tmp/adaptive-times.tsv') as f:
    for arm,test,rep,t in csv.reader(f,delimiter='\t'):
        rows[(arm,test)].append(float(t))

tests=sorted({t for _,t in rows})
arms=['baseline','left','right','shorter']
print('MEDIANS_SECONDS')
for test in tests:
    vals=[]
    for arm in arms:
        m=statistics.median(rows[(arm,test)])
        vals.append((arm,m))
    b=dict(vals)['baseline']
    print(test)
    for arm,m in vals:
        print(f'  {arm:8s} {m:.6f}  ratio_vs_baseline={m/b:.6f} delta={(m/b-1)*100:+.3f}%')

mb={a:statistics.median(rows[(a,'mathlib')]) for a in arms}
b=mb['baseline']
best=min((v,a) for a,v in mb.items() if a!='baseline')
ratio=best[0]/b
print('MATHLIB',mb)
print('BEST_CANDIDATE',best[1],best[0])
print('BEST_RATIO',ratio)
if ratio <= 0.85:
    print('DECISION=PHASE_CHANGE__FULL_SEMANTIC_GATE_WINNER')
elif ratio <= 0.95:
    print('DECISION=MATERIAL_GAIN__FULL_SEMANTIC_GATE_WINNER')
elif ratio <= 0.99:
    print('DECISION=SMALL_GAIN__FULL_SEMANTIC_GATE_WINNER')
else:
    print('DECISION=NO_MATHLIB_GAIN__REJECT_EQUAL_HINT_SCHEDULER')
PY

# Full semantic gate only if a candidate beats baseline by >=1% on Mathlib.
WINNER=$(python3 - <<'PY'
import csv,statistics
from collections import defaultdict
r=defaultdict(list)
with open('/tmp/adaptive-times.tsv') as f:
  for a,t,rep,x in csv.reader(f,delimiter='\t'):
    if t=='mathlib': r[a].append(float(x))
b=statistics.median(r['baseline'])
cands=[(statistics.median(v),a) for a,v in r.items() if a!='baseline']
v,a=min(cands)
print(a if v <= .99*b else '')
PY
)

if [ -n "$WINNER" ]; then
  nix develop -c ./lka.py build-test --all
  : > /tmp/semantic-gate.txt
  while IFS= read -r f; do
    case "$f" in *.ndjson) ;; *) continue ;; esac
    bstatus=0; wstatus=0
    timeout 120 /tmp/mg-baseline /tmp/checker.json < "$f" >/tmp/base.out 2>/tmp/base.err || bstatus=$?
    timeout 120 "/tmp/mg-$WINNER" /tmp/checker.json < "$f" >/tmp/win.out 2>/tmp/win.err || wstatus=$?
    if [ "$bstatus" -ne "$wstatus" ]; then
      printf 'MISMATCH\t%s\tbase=%s\twinner=%s\n' "$f" "$bstatus" "$wstatus" | tee -a /tmp/semantic-gate.txt
      exit 1
    fi
    printf 'MATCH\t%s\tstatus=%s\n' "$f" "$bstatus" >> /tmp/semantic-gate.txt
  done < <(find _build/tests -maxdepth 1 -type f -name '*.ndjson' | sort)
  echo "SEMANTIC_GATE_PASS winner=$WINNER" | tee -a /tmp/semantic-gate.txt
else
  echo 'SEMANTIC_GATE_SKIPPED no >=1% Mathlib winner' > /tmp/semantic-gate.txt
fi

cp /tmp/adaptive-times.tsv /tmp/adaptive-decision.txt /tmp/semantic-gate.txt "$ROOT"/
