#!/usr/bin/env bash
set -euxo pipefail
V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
ROOT=$(pwd)
rm -rf /tmp/mg-pair-census /tmp/arena-pair-census

git worktree add /tmp/mg-pair-census "$V2"
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/mg-pair-census/src/conv.rs')
s=p.read_text()
old='''                    } else {\n                        self.unfold_pair(depth, t, t2)\n                    }\n'''
new='''                    } else {\n                        let lx = sx.len();\n                        let ly = sy.len();\n                        let gap = if lx >= ly { lx - ly } else { ly - lx };\n                        if gap >= 2 {\n                            let (shorter, longer) = if lx <= ly { (lx, ly) } else { (ly, lx) };\n                            if lx <= ly {\n                                let v1 = self.unfold_value(depth, t);\n                                let first_changed = !std::ptr::eq(v1, t);\n                                eprintln!(\"MGPAIR shorter={} longer={} gap={} first_changed={} side=L\", shorter, longer, gap, first_changed);\n                                if first_changed { return self.unify::<true>(depth, v1, t2); }\n                                let v2 = self.unfold_value(depth, t2);\n                                let second_changed = !std::ptr::eq(v2, t2);\n                                eprintln!(\"MGSECOND shorter={} longer={} gap={} second_changed={} side=R\", shorter, longer, gap, second_changed);\n                                if second_changed { return self.unify::<true>(depth, t, v2); }\n                            } else {\n                                let v2 = self.unfold_value(depth, t2);\n                                let first_changed = !std::ptr::eq(v2, t2);\n                                eprintln!(\"MGPAIR shorter={} longer={} gap={} first_changed={} side=R\", shorter, longer, gap, first_changed);\n                                if first_changed { return self.unify::<true>(depth, t, v2); }\n                                let v1 = self.unfold_value(depth, t);\n                                let second_changed = !std::ptr::eq(v1, t);\n                                eprintln!(\"MGSECOND shorter={} longer={} gap={} second_changed={} side=L\", shorter, longer, gap, second_changed);\n                                if second_changed { return self.unify::<true>(depth, v1, t2); }\n                            }\n                        }\n                        self.unfold_pair(depth, t, t2)\n                    }\n'''
anchor='''                    } else if rh.is_lt(&lh) {'''
pos=s.index(anchor)
target=s.index(old,pos)
s=s[:target]+s[target:].replace(old,new,1)
p.write_text(s)
PY
cd /tmp/mg-pair-census
cargo test --release --locked
RUSTFLAGS='-C target-cpu=x86-64' cargo build --release --locked
cp target/release/sokonanoda /tmp/mg-pair-census-bin
cat >/tmp/checker.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/arena-pair-census
cd /tmp/arena-pair-census
for t in perf/app-lam perf/beta-ladder perf/let-ladder perf/grind-ring-5 perf/folded-constant-first perf/folded-constant-last perf/args-before-unfold perf/unroll-versus-evaluate perf/refute-cheap-first perf/refute-cheap-last; do
  nix develop -c ./lka.py build-test "$t"
done
: > /tmp/pair-events.log
for f in _build/tests/perf/*.ndjson; do
  timeout 120 /tmp/mg-pair-census-bin /tmp/checker.json < "$f" >/dev/null 2>>/tmp/pair-events.log || true
done
python3 - <<'PY' | tee /tmp/pair-census-summary.txt
from collections import Counter,defaultdict
import re
pair=Counter(); first=Counter(); second=Counter(); side=Counter()
pat=re.compile(r'MGPAIR shorter=(\d+) longer=(\d+) gap=(\d+) first_changed=(true|false) side=([LR])')
pat2=re.compile(r'MGSECOND shorter=(\d+) longer=(\d+) gap=(\d+) second_changed=(true|false) side=([LR])')
for line in open('/tmp/pair-events.log',errors='ignore'):
    m=pat.search(line)
    if m:
      a,b,g,ch,sd=m.groups(); key=(int(a),int(b)); pair[key]+=1; first[(key,ch)]+=1; side[sd]+=1
    m=pat2.search(line)
    if m:
      a,b,g,ch,sd=m.groups(); key=(int(a),int(b)); second[(key,ch)]+=1
print('TOTAL_GAP2_EVENTS',sum(pair.values()))
print('TOP_PAIRS')
for (a,b),n in pair.most_common(30):
    ft=first[((a,b),'true')]; ff=first[((a,b),'false')]
    st=second[((a,b),'true')]; sf=second[((a,b),'false')]
    print(f'{a},{b}\tcount={n}\tfirst_hit={ft}\tfirst_miss={ff}\tsecond_hit={st}\tsecond_miss={sf}')
print('SIDE_FIRST',dict(side))
print('SHORTER_BANDS')
bands=defaultdict(int)
for (a,b),n in pair.items():
    if a==0: bands['short0']+=n
    if a<=1: bands['short<=1']+=n
    if a<=2: bands['short<=2']+=n
    if b>=4: bands['long>=4']+=n
for k,v in sorted(bands.items()): print(k,v)
PY
cp /tmp/pair-census-summary.txt /tmp/pair-events.log "$ROOT"/
