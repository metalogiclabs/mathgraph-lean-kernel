#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
ARENA=f0fe3b379dbce91537417b529140d0ca250f271c
rm -rf /tmp/v20-base /tmp/v20-compound /tmp/v20-arena /tmp/v20-*-target

git worktree add /tmp/v20-base "$BASE"
cp -a /tmp/v20-base /tmp/v20-compound
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v20-compound/src/eval.rs'); s=p.read_text()
pi_old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
pi_new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) {\n            return v;\n        }\n        if let Some(r) = self.store_lookup(depth, v) {"""
old='''    pub(crate) fn apply_many(&mut self, depth: u32, f0: V<'t>, args: &[V<'t>]) -> V<'t> {
        let mut f = f0;
        let mut i = 0usize;
        while i < args.len() {
            let Value::Lam { body: clo, .. } = f else {
                f = self.apply(depth, f, args[i]);
                i += 1;
                continue
            };
            let mut env = value::env_extend(self.arena, clo.env, args[i]);
            let mut body = clo.body;
            i += 1;
            while i < args.len() {
                let Expr::Lambda { body: inner, .. } = self.ctx.read_expr(body) else { break };
                let pruned = self.key_env(env, body);
                env = value::env_extend(self.arena, pruned, args[i]);
                body = inner;
                i += 1;
            }
            f = self.eval(depth, env, body);
        }
        f
    }
'''
new='''    pub(crate) fn apply_many(&mut self, depth: u32, f0: V<'t>, args: &[V<'t>]) -> V<'t> {
        let mut f = f0;
        let mut i = 0usize;
        while i < args.len() {
            let Value::Lam { body: clo, .. } = f else {
                f = self.apply(depth, f, args[i]);
                i += 1;
                continue
            };
            let first_i = i;
            let mut env = value::env_extend(self.arena, clo.env, args[i]);
            let mut body = clo.body;
            i += 1;
            let rem = args.len().saturating_sub(i);
            if rem > 0 && rem <= 2 {
                let mut scan_body = body;
                let mut scan_i = i;
                while scan_i < args.len() {
                    let Expr::Lambda { body: inner, .. } = self.ctx.read_expr(scan_body) else { break };
                    scan_body = inner;
                    scan_i += 1;
                }
                if scan_i == args.len() {
                    if let Expr::Var { dbj_idx, .. } = self.ctx.read_expr(scan_body) {
                        let supplied = 1usize + rem;
                        let d = dbj_idx as usize;
                        let v = if d < supplied { args[first_i + supplied - 1 - d] } else { clo.env.lookup((d - supplied) as u16).expect("v20 loose bvar") };
                        f = self.force_thunk(depth, v);
                        i = scan_i;
                        continue;
                    }
                }
            }
            while i < args.len() {
                let Expr::Lambda { body: inner, .. } = self.ctx.read_expr(body) else { break };
                let pruned = self.key_env(env, body);
                env = value::env_extend(self.arena, pruned, args[i]);
                body = inner;
                i += 1;
            }
            f = self.eval(depth, env, body);
        }
        f
    }
'''
assert s.count(pi_old)==1
s=s.replace(pi_old,pi_new,1)
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
print('V20_COMPOUND_PATCH=APPLIED')
PY

for arm in base compound; do
  (cd /tmp/v20-$arm && cargo test --release --locked)
  (cd /tmp/v20-$arm && CARGO_TARGET_DIR=/tmp/v20-$arm-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked)
  cp /tmp/v20-$arm-target/release/sokonanoda /tmp/v20-$arm-bin
done
printf '%s\n' '{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}' >/tmp/v20-checker.json

git clone https://github.com/leanprover/lean-kernel-arena /tmp/v20-arena
cd /tmp/v20-arena
git checkout "$ARENA"
nix develop -c ./lka.py build-test

python3 - <<'PY'
import pathlib, subprocess, yaml, sys, json
root=pathlib.Path('/tmp/v20-arena')
rows=[]; bad=[]; tested=0
for y in sorted((root/'tests').glob('*.yaml')):
    d=yaml.safe_load(y.read_text()) or {}
    outcome=d.get('outcome')
    if outcome not in ('accept','reject'): continue
    name=y.stem
    fs=list((root/'_build/tests').glob(name+'.ndjson'))+list((root/'_build/tests').glob(name+'/**/*.ndjson'))
    for f in fs:
        tested+=1
        with f.open('rb') as inp:
            p=subprocess.run(['/tmp/v20-compound-bin','/tmp/v20-checker.json'],stdin=inp,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        accepted=p.returncode==0
        ok=accepted if outcome=='accept' else not accepted
        rows.append(f'{name}\t{outcome}\trc={p.returncode}\t'+('PASS' if ok else 'FAIL'))
        if not ok: bad.append((name,outcome,p.returncode,p.stderr.decode(errors='replace')[-2000:]))
pathlib.Path('/tmp/v20-full-arena-results.tsv').write_text('\n'.join(rows)+'\n')
pathlib.Path('/tmp/v20-full-arena-decision.txt').write_text(f'tests={tested}\nfailures={len(bad)}\nDECISION='+('FULL_ARENA_GREEN__COMPOUND_PROVISIONALLY_PROMOTABLE' if not bad else 'FULL_ARENA_NOT_GREEN')+'\n')
if bad:
    pathlib.Path('/tmp/v20-full-arena-failures.txt').write_text('\n\n'.join(map(str,bad)))
    print(*bad,sep='\n'); sys.exit(1)
print(f'FULL_ARENA_GREEN tests={tested}')
PY

nix develop -c ./lka.py build-test perf/grind-ring-5
nix shell github:NixOS/nixpkgs/0ad6f47ea4fe188f4bc8f0380f93ae8523337c6c#valgrind -c bash -lc '
set -euo pipefail
cd /tmp/v20-arena
F=_build/tests/perf/grind-ring-5.ndjson
for arm in base compound; do
  valgrind --tool=callgrind --callgrind-out-file=/tmp/v20-$arm-grind.cg /tmp/v20-$arm-bin /tmp/v20-checker.json < "$F" >/dev/null 2>/tmp/v20-$arm-grind.vg
  grep "^summary:" /tmp/v20-$arm-grind.cg
 done
callgrind_annotate --inclusive=yes --threshold=0.3 /tmp/v20-compound-grind.cg > /tmp/v20-compound-hotspots.txt
'
python3 - <<'PY' | tee /tmp/v20-residual-decision.txt
from pathlib import Path

def summary(p):
    for l in Path(p).read_text(errors='replace').splitlines():
        if l.startswith('summary:'): return int(l.split()[1])
b=summary('/tmp/v20-base-grind.cg'); c=summary('/tmp/v20-compound-grind.cg')
q=(c/b-1)*100
print(f'grind_ring_5 compound={c} base={b} delta={q:+.4f}%')
print('DECISION=FULL_GATE_GREEN__READ_POST_COMPOUND_HOTSPOT_ATLAS')
print('POST_COMPOUND_HOTSPOTS_BEGIN')
text=Path('/tmp/v20-compound-hotspots.txt').read_text(errors='replace')
for l in text.splitlines()[:120]: print(l)
PY
