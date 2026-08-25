#!/usr/bin/env bash
set -euxo pipefail
V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
ROOT=$(pwd)
rm -rf /tmp/mg-pair-* /tmp/arena-pair

for arm in baseline gap2 short0 shortle1 shortle2 longge4; do
  git worktree add "/tmp/mg-pair-$arm" "$V2"
done

python3 - <<'PY'
from pathlib import Path
old='''                    } else {\n                        self.unfold_pair(depth, t, t2)\n                    }\n'''

def repl(cond):
    return f'''                    }} else {{\n                        let lx = sx.len();\n                        let ly = sy.len();\n                        let gap = if lx >= ly {{ lx - ly }} else {{ ly - lx }};\n                        let shorter = lx.min(ly);\n                        let longer = lx.max(ly);\n                        if {cond} {{\n                            if lx <= ly {{\n                                let v1 = self.unfold_value(depth, t);\n                                if !std::ptr::eq(v1, t) {{ return self.unify::<true>(depth, v1, t2); }}\n                                let v2 = self.unfold_value(depth, t2);\n                                if !std::ptr::eq(v2, t2) {{ return self.unify::<true>(depth, t, v2); }}\n                            }} else {{\n                                let v2 = self.unfold_value(depth, t2);\n                                if !std::ptr::eq(v2, t2) {{ return self.unify::<true>(depth, t, v2); }}\n                                let v1 = self.unfold_value(depth, t);\n                                if !std::ptr::eq(v1, t) {{ return self.unify::<true>(depth, v1, t2); }}\n                            }}\n                        }}\n                        self.unfold_pair(depth, t, t2)\n                    }}\n'''

conds={
 'gap2':'gap >= 2',
 'short0':'gap >= 2 && shorter == 0',
 'shortle1':'gap >= 2 && shorter <= 1',
 'shortle2':'gap >= 2 && shorter <= 2',
 'longge4':'gap >= 2 && longer >= 4',
}
for arm,cond in conds.items():
    p=Path(f'/tmp/mg-pair-{arm}/src/conv.rs')
    s=p.read_text()
    anchor='''                    } else if rh.is_lt(&lh) {'''
    pos=s.index(anchor)
    target=s.index(old,pos)
    s=s[:target]+s[target:].replace(old,repl(cond),1)
    p.write_text(s)
PY

for arm in baseline gap2 short0 shortle1 shortle2 longge4; do
  cd "/tmp/mg-pair-$arm"
  cargo test --release --locked
  RUSTFLAGS='-C target-cpu=x86-64' cargo build --release --locked
  cp target/release/sokonanoda "/tmp/mg-$arm"
done

cat >/tmp/checker.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/arena-pair
cd /tmp/arena-pair
nix develop -c ./lka.py build-test mathlib

: > /tmp/pair-times.tsv
measure () {
  local arm=$1 rep=$2
  /usr/bin/time -q -f '%e' -o /tmp/time.txt "/tmp/mg-$arm" /tmp/checker.json < _build/tests/mathlib.ndjson >/tmp/${arm}-${rep}.out 2>/tmp/${arm}-${rep}.err
  printf '%s\t%s\t%s\n' "$arm" "$rep" "$(tail -n 1 /tmp/time.txt)" >> /tmp/pair-times.tsv
}
orders=(
"baseline gap2 short0 shortle1 shortle2 longge4"
"longge4 shortle2 shortle1 short0 gap2 baseline"
"shortle1 baseline longge4 gap2 shortle2 short0"
)
rep=0
for order in "${orders[@]}"; do
  rep=$((rep+1))
  for arm in $order; do measure "$arm" "$rep"; done
done

python3 - <<'PY' | tee /tmp/pair-decision.txt
import csv, statistics
from collections import defaultdict
r=defaultdict(list)
with open('/tmp/pair-times.tsv') as f:
    for a,rep,x in csv.reader(f,delimiter='\t'): r[a].append(float(x))
arms=['baseline','gap2','short0','shortle1','shortle2','longge4']
med={a:statistics.median(r[a]) for a in arms}
b=med['baseline']
print('MATHLIB_MEDIANS_SECONDS')
for a in arms:
    print(f'{a:9s} {med[a]:.3f} ratio={med[a]/b:.6f} delta={(med[a]/b-1)*100:+.3f}% reps={r[a]}')
best=min((med[a],a) for a in arms if a!='baseline')
print('BEST',best[1],best[0],'ratio',best[0]/b)
print('DELTA_VS_GAP2', (best[0]/med['gap2']-1)*100)
if best[0] <= .95*b: print('DECISION=MATERIAL_JUMP')
elif best[0] < med['gap2']: print('DECISION=JUMP_OVER_GAP2')
elif best[0] <= .99*b: print('DECISION=RETAIN_GAP2_NO_FURTHER_JUMP')
else: print('DECISION=NO_STABLE_GAIN')
PY

WINNER=$(python3 - <<'PY'
import csv,statistics
from collections import defaultdict
r=defaultdict(list)
with open('/tmp/pair-times.tsv') as f:
  for a,rep,x in csv.reader(f,delimiter='\t'): r[a].append(float(x))
b=statistics.median(r['baseline'])
c=[(statistics.median(v),a) for a,v in r.items() if a!='baseline']
v,a=min(c)
print(a if v <= .99*b else '')
PY
)

: > /tmp/pair-semantic-gate.txt
if [ -n "$WINNER" ]; then
  nix develop -c ./lka.py build-test
  while IFS= read -r f; do
    bstatus=0; wstatus=0
    timeout 120 /tmp/mg-baseline /tmp/checker.json < "$f" >/tmp/base.out 2>/tmp/base.err || bstatus=$?
    timeout 120 "/tmp/mg-$WINNER" /tmp/checker.json < "$f" >/tmp/win.out 2>/tmp/win.err || wstatus=$?
    if [ "$bstatus" -ne "$wstatus" ]; then
      printf 'MISMATCH\t%s\tbase=%s\twinner=%s\n' "$f" "$bstatus" "$wstatus" | tee -a /tmp/pair-semantic-gate.txt
      exit 1
    fi
    printf 'MATCH\t%s\tstatus=%s\n' "$f" "$bstatus" >> /tmp/pair-semantic-gate.txt
  done < <(find _build/tests -maxdepth 1 -type f -name '*.ndjson' | sort)
  echo "SEMANTIC_GATE_PASS winner=$WINNER" | tee -a /tmp/pair-semantic-gate.txt
else
  echo 'SEMANTIC_GATE_SKIPPED no >=1% Mathlib winner' > /tmp/pair-semantic-gate.txt
fi

cp /tmp/pair-times.tsv /tmp/pair-decision.txt /tmp/pair-semantic-gate.txt "$ROOT"/
