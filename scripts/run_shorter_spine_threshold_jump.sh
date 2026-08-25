#!/usr/bin/env bash
set -euxo pipefail
V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
ROOT=$(pwd)
rm -rf /tmp/mg-jump-* /tmp/arena-jump

for arm in baseline all gap1 gap2 gap4; do
  git worktree add "/tmp/mg-jump-$arm" "$V2"
done

python3 - <<'PY'
from pathlib import Path

old = '''                    } else {
                        self.unfold_pair(depth, t, t2)
                    }
'''

def replacement(threshold):
    cond = 'true' if threshold == 0 else f'gap >= {threshold}'
    return f'''                    }} else {{
                        // Causal threshold ablation of the validated shorter-spine scheduler.
                        // Only intervene when the structural spine-length asymmetry is large enough.
                        let lx = sx.len();
                        let ly = sy.len();
                        let gap = if lx >= ly {{ lx - ly }} else {{ ly - lx }};
                        if {cond} {{
                            if lx <= ly {{
                                let v1 = self.unfold_value(depth, t);
                                if !std::ptr::eq(v1, t) {{
                                    return self.unify::<true>(depth, v1, t2);
                                }}
                                let v2 = self.unfold_value(depth, t2);
                                if !std::ptr::eq(v2, t2) {{
                                    return self.unify::<true>(depth, t, v2);
                                }}
                            }} else {{
                                let v2 = self.unfold_value(depth, t2);
                                if !std::ptr::eq(v2, t2) {{
                                    return self.unify::<true>(depth, t, v2);
                                }}
                                let v1 = self.unfold_value(depth, t);
                                if !std::ptr::eq(v1, t) {{
                                    return self.unify::<true>(depth, v1, t2);
                                }}
                            }}
                        }}
                        self.unfold_pair(depth, t, t2)
                    }}
'''

for arm, threshold in [('all',0),('gap1',1),('gap2',2),('gap4',4)]:
    p=Path(f'/tmp/mg-jump-{arm}/src/conv.rs')
    s=p.read_text()
    anchor='''                    } else if rh.is_lt(&lh) {'''
    pos=s.index(anchor)
    target=s.index(old,pos)
    s=s[:target]+s[target:].replace(old,replacement(threshold),1)
    p.write_text(s)
PY

for arm in baseline all gap1 gap2 gap4; do
  cd "/tmp/mg-jump-$arm"
  cargo test --release --locked
  RUSTFLAGS='-C target-cpu=x86-64' cargo build --release --locked
  cp target/release/sokonanoda "/tmp/mg-$arm"
done

cat >/tmp/checker.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/arena-jump
cd /tmp/arena-jump
nix develop -c ./lka.py build-test mathlib

: > /tmp/jump-times.tsv
measure () {
  local arm=$1 rep=$2
  local tm
  tm=$(/usr/bin/time -q -f '%e' -o /tmp/time.txt "/tmp/mg-$arm" /tmp/checker.json < _build/tests/mathlib.ndjson >/tmp/${arm}-${rep}.out 2>/tmp/${arm}-${rep}.err; tail -n 1 /tmp/time.txt)
  printf '%s\t%s\t%s\n' "$arm" "$rep" "$tm" >> /tmp/jump-times.tsv
}

orders=(
  "baseline all gap1 gap2 gap4"
  "gap4 gap2 gap1 all baseline"
  "gap2 baseline gap4 all gap1"
)
rep=0
for order in "${orders[@]}"; do
  rep=$((rep+1))
  for arm in $order; do measure "$arm" "$rep"; done
done

python3 - <<'PY' | tee /tmp/jump-decision.txt
import csv, statistics
from collections import defaultdict
r=defaultdict(list)
with open('/tmp/jump-times.tsv') as f:
    for arm,rep,t in csv.reader(f,delimiter='\t'):
        r[arm].append(float(t))
arms=['baseline','all','gap1','gap2','gap4']
med={a:statistics.median(r[a]) for a in arms}
b=med['baseline']
print('MATHLIB_MEDIANS_SECONDS')
for a in arms:
    m=med[a]
    print(f'{a:8s} {m:.3f} ratio={m/b:.6f} delta={(m/b-1)*100:+.3f}% reps={r[a]}')
best_v,best_a=min((med[a],a) for a in arms if a!='baseline')
ratio=best_v/b
print('BEST',best_a,best_v,'ratio',ratio)
if ratio <= .85:
    print('DECISION=PHASE_CHANGE')
elif ratio <= .95:
    print('DECISION=MATERIAL_JUMP')
elif ratio <= .975:
    print('DECISION=JUMP_OVER_PREVIOUS')
elif ratio <= .99:
    print('DECISION=RETAIN_SMALL_GAIN')
else:
    print('DECISION=NO_GAIN')
PY

WINNER=$(python3 - <<'PY'
import csv,statistics
from collections import defaultdict
r=defaultdict(list)
with open('/tmp/jump-times.tsv') as f:
  for a,rep,x in csv.reader(f,delimiter='\t'): r[a].append(float(x))
b=statistics.median(r['baseline'])
v,a=min((statistics.median(v),a) for a,v in r.items() if a!='baseline')
print(a if v <= .99*b else '')
PY
)

if [ -n "$WINNER" ]; then
  nix develop -c ./lka.py build-test
  : > /tmp/jump-semantic-gate.txt
  while IFS= read -r f; do
    bstatus=0; wstatus=0
    timeout 120 /tmp/mg-baseline /tmp/checker.json < "$f" >/tmp/base.out 2>/tmp/base.err || bstatus=$?
    timeout 120 "/tmp/mg-$WINNER" /tmp/checker.json < "$f" >/tmp/win.out 2>/tmp/win.err || wstatus=$?
    if [ "$bstatus" -ne "$wstatus" ]; then
      printf 'MISMATCH\t%s\tbase=%s\twinner=%s\n' "$f" "$bstatus" "$wstatus" | tee -a /tmp/jump-semantic-gate.txt
      exit 1
    fi
    printf 'MATCH\t%s\tstatus=%s\n' "$f" "$bstatus" >> /tmp/jump-semantic-gate.txt
  done < <(find _build/tests -maxdepth 1 -type f -name '*.ndjson' | sort)
  echo "SEMANTIC_GATE_PASS winner=$WINNER" | tee -a /tmp/jump-semantic-gate.txt
else
  echo 'SEMANTIC_GATE_SKIPPED no >=1% winner' > /tmp/jump-semantic-gate.txt
fi

cp /tmp/jump-times.tsv /tmp/jump-decision.txt /tmp/jump-semantic-gate.txt "$ROOT"/
