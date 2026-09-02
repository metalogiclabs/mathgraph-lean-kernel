#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
ARENA=f0fe3b379dbce91537417b529140d0ca250f271c
rm -rf /tmp/v14 /tmp/v14-arena /tmp/v14-target /tmp/v14-base-target
git worktree add /tmp/v14 "$BASE"
cd /tmp/v14
cargo test --locked
python3 - <<'PY'
from pathlib import Path
p=Path('src/eval.rs'); s=p.read_text()
anchor='''    fn fire_recursor(\n        &mut self, depth: u32,\n'''
helpers='''    #[inline(never)]\n    fn v14_apply_prefix(&mut self, depth: u32, v: V<'t>, xs: &[V<'t>]) -> V<'t> {\n        self.apply_many(depth, v, xs)\n    }\n\n    #[inline(never)]\n    fn v14_apply_ctor_fields(&mut self, depth: u32, v: V<'t>, xs: &[V<'t>]) -> V<'t> {\n        self.apply_many(depth, v, xs)\n    }\n\n    #[inline(never)]\n    fn v14_apply_suffix(&mut self, depth: u32, v: V<'t>, xs: &[V<'t>]) -> V<'t> {\n        self.apply_many(depth, v, xs)\n    }\n\n    fn fire_recursor(\n        &mut self, depth: u32,\n'''
assert s.count(anchor)==1; s=s.replace(anchor,helpers,1)
s=s.replace('''        result = self.apply_many(depth, result, &args[..nprefix]);\n        result = self.apply_many(depth, result, &ctor_args[num_extra..]);\n        result = self.apply_many(depth, result, &args[rec.major_idx() + 1..]);''','''        result = self.v14_apply_prefix(depth, result, &args[..nprefix]);\n        result = self.v14_apply_ctor_fields(depth, result, &ctor_args[num_extra..]);\n        result = self.v14_apply_suffix(depth, result, &args[rec.major_idx() + 1..]);''',1)
p.write_text(s)
PY
CARGO_TARGET_DIR=/tmp/v14-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked
cp /tmp/v14-target/release/sokonanoda /tmp/v14-phase-bin
printf '%s\n' '{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}' >/tmp/v14-checker.json
git clone https://github.com/leanprover/lean-kernel-arena /tmp/v14-arena
cd /tmp/v14-arena
git checkout "$ARENA"
for T in perf/app-lam perf/beta-ladder perf/let-ladder perf/grind-ring-5; do nix develop -c ./lka.py build-test "$T"; done
cd /tmp/v14
git checkout -- src/eval.rs
CARGO_TARGET_DIR=/tmp/v14-base-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked
cp /tmp/v14-base-target/release/sokonanoda /tmp/v14-base-bin
python3 - <<'PY'
import subprocess
arena='/tmp/v14-arena/_build/tests'
for t in ['perf/app-lam','perf/beta-ladder','perf/let-ladder','perf/grind-ring-5']:
    inp=open(f'{arena}/{t}.ndjson','rb').read()
    b=subprocess.run(['/tmp/v14-base-bin','/tmp/v14-checker.json'],input=inp,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    a=subprocess.run(['/tmp/v14-phase-bin','/tmp/v14-checker.json'],input=inp,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    assert a.stdout==b.stdout,t
print('SEMANTIC_REPLAY=EXACT')
PY
sudo apt-get update -qq
sudo apt-get install -y -qq valgrind
F=/tmp/v14-arena/_build/tests/perf/grind-ring-5.ndjson
valgrind --tool=callgrind --callgrind-out-file=/tmp/v14-callgrind.out /tmp/v14-phase-bin /tmp/v14-checker.json < "$F" >/dev/null 2>/tmp/v14-vg.txt
callgrind_annotate --inclusive=yes --auto=no /tmp/v14-callgrind.out > /tmp/v14-callgrind.txt
python3 - <<'PY'
from pathlib import Path
import re,json
text=Path('/tmp/v14-callgrind.txt').read_text(errors='replace')
pat=re.compile(r'^\s*([0-9,]+)\s+\(\s*([0-9.]+)%\).*?(v14_apply_prefix|v14_apply_ctor_fields|v14_apply_suffix|fire_recursor)',re.M)
rows=[]
for m in pat.finditer(text): rows.append({'instructions':int(m.group(1).replace(',','')),'pct':float(m.group(2)),'phase':m.group(3)})
# first occurrence per symbol is inclusive summary
seen={}
for r in rows:
    seen.setdefault(r['phase'],r)
rank=sorted(seen.values(),key=lambda r:r['instructions'],reverse=True)
json.dump({'phases':rank},open('/tmp/v14-phase-cost.json','w'),indent=2)
for r in rank: print('PHASE',r)
subs=[r for r in rank if r['phase'].startswith('v14_apply_')]
if subs:
    win=max(subs,key=lambda r:r['instructions'])
    print('DOMINANT_FIRE_PHASE='+win['phase'])
    grammar={
      'v14_apply_prefix':['prefix argument role','closure head after each prefix apply','shared prefix across repeated fires'],
      'v14_apply_ctor_fields':['constructor telescope position','recursive-vs-nonrecursive field','field projection reuse'],
      'v14_apply_suffix':['suffix length','post-major application role','continuation demand']
    }[win['phase']]
    res={'residual':'successful recursor firing dominated by one application phase','dominant_phase':win,'next_grammar':grammar,'promotion':'NONE_MEASUREMENT_ONLY'}
    json.dump(res,open('/tmp/v14-residual.json','w'),indent=2)
    Path('/tmp/v14-decision.txt').write_text('DOMINANT_FIRE_PHASE='+win['phase']+'\nNEXT_GRAMMAR='+','.join(grammar)+'\nDECISION=BUILD_PHASE_SPECIFIC_SEPARATOR\nPROMOTION=NONE\n')
else:
    raise SystemExit('phase symbols not found in callgrind annotation')
PY
