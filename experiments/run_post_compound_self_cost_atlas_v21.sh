#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
ARENA=f0fe3b379dbce91537417b529140d0ca250f271c
rm -rf /tmp/v21-base /tmp/v21-compound /tmp/v21-arena /tmp/v21-*-target

git worktree add /tmp/v21-base "$BASE"
cp -a /tmp/v21-base /tmp/v21-compound
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v21-compound/src/eval.rs'); s=p.read_text()
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
                        let v = if d < supplied { args[first_i + supplied - 1 - d] } else { clo.env.lookup((d - supplied) as u16).expect("v21 loose bvar") };
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
print('V21_COMPOUND_PATCH=APPLIED')
PY
for arm in base compound; do
  (cd /tmp/v21-$arm && cargo test --release --locked)
  (cd /tmp/v21-$arm && CARGO_TARGET_DIR=/tmp/v21-$arm-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked)
  cp /tmp/v21-$arm-target/release/sokonanoda /tmp/v21-$arm-bin
done
printf '%s\n' '{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}' >/tmp/v21-checker.json

git clone https://github.com/leanprover/lean-kernel-arena /tmp/v21-arena
cd /tmp/v21-arena
git checkout "$ARENA"
nix develop -c ./lka.py build-test perf/grind-ring-5
F=_build/tests/perf/grind-ring-5.ndjson
/tmp/v21-base-bin /tmp/v21-checker.json < "$F" >/tmp/v21-base.out 2>/tmp/v21-base.err
/tmp/v21-compound-bin /tmp/v21-checker.json < "$F" >/tmp/v21-compound.out 2>/tmp/v21-compound.err
cmp /tmp/v21-base.out /tmp/v21-compound.out
echo SEMANTIC_REPLAY=EXACT | tee /tmp/v21-semantic.txt

nix shell github:NixOS/nixpkgs/0ad6f47ea4fe188f4bc8f0380f93ae8523337c6c#valgrind -c bash -lc '
set -euo pipefail
cd /tmp/v21-arena
F=_build/tests/perf/grind-ring-5.ndjson
valgrind --tool=callgrind --callgrind-out-file=/tmp/v21-compound.cg /tmp/v21-compound-bin /tmp/v21-checker.json < "$F" >/dev/null 2>/tmp/v21-compound.vg
callgrind_annotate --inclusive=no --show=Ir --sort=Ir --threshold=0.15 /tmp/v21-compound.cg > /tmp/v21-self-hotspots.txt
'
python3 - <<'PY' | tee /tmp/v21-decision.txt
from pathlib import Path
text=Path('/tmp/v21-self-hotspots.txt').read_text(errors='replace')
print('MEASUREMENT=EXCLUSIVE_SELF_INSTRUCTIONS')
print('SEMANTIC_REPLAY=EXACT')
print('POST_COMPOUND_SELF_HOTSPOTS_BEGIN')
lines=text.splitlines()
start=0
for i,l in enumerate(lines):
    if 'file:function' in l:
        start=i+2; break
shown=0
for l in lines[start:]:
    if not l.strip():
        if shown: break
        continue
    if '%' in l and ':' in l:
        print(l)
        shown+=1
        if shown>=40: break
print('POST_COMPOUND_SELF_HOTSPOTS_END')
print('DECISION=SELECT_LARGEST_NON_INCUMBENT_SELF_COST_BASIN')
PY
