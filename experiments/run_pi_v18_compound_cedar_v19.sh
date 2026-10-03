#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
ARENA=f0fe3b379dbce91537417b529140d0ca250f271c
rm -rf /tmp/v19-base /tmp/v19-pi /tmp/v19-v18 /tmp/v19-compound /tmp/v19-arena /tmp/v19-*-target

git worktree add /tmp/v19-base "$BASE"
cp -a /tmp/v19-base /tmp/v19-pi
cp -a /tmp/v19-base /tmp/v19-v18
cp -a /tmp/v19-base /tmp/v19-compound

python3 - <<'PY'
from pathlib import Path
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
                        let v = if d < supplied {
                            args[first_i + supplied - 1 - d]
                        } else {
                            clo.env.lookup((d - supplied) as u16).expect("apply_many v19: loose bvar")
                        };
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
for arm in ('pi','compound'):
    p=Path(f'/tmp/v19-{arm}/src/eval.rs'); s=p.read_text(); assert s.count(pi_old)==1,(arm,'pi',s.count(pi_old)); p.write_text(s.replace(pi_old,pi_new,1))
for arm in ('v18','compound'):
    p=Path(f'/tmp/v19-{arm}/src/eval.rs'); s=p.read_text(); assert s.count(old)==1,(arm,'v18',s.count(old)); p.write_text(s.replace(old,new,1))
print('V19_PATCHES=APPLIED')
PY

for arm in base pi v18 compound; do
  (cd /tmp/v19-$arm && cargo test --locked)
  (cd /tmp/v19-$arm && CARGO_TARGET_DIR=/tmp/v19-$arm-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked)
  cp /tmp/v19-$arm-target/release/sokonanoda /tmp/v19-$arm-bin
done
printf '%s\n' '{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}' >/tmp/v19-checker.json

git clone https://github.com/leanprover/lean-kernel-arena /tmp/v19-arena
cd /tmp/v19-arena
git checkout "$ARENA"
nix develop -c ./lka.py build-test cedar
for T in perf/app-lam perf/beta-ladder perf/grind-ring-5; do nix develop -c ./lka.py build-test "$T"; done
head -n 1000000 _build/tests/cedar.ndjson >/tmp/v19-cedar-1m.ndjson

for spec in cedar:_build/tests/cedar.ndjson app-lam:_build/tests/perf/app-lam.ndjson beta-ladder:_build/tests/perf/beta-ladder.ndjson grind-ring-5:_build/tests/perf/grind-ring-5.ndjson; do
  T=${spec%%:*}; F=${spec#*:}
  /tmp/v19-base-bin /tmp/v19-checker.json < "$F" >/tmp/v19-base-$T.out 2>/tmp/v19-base-$T.err
  for arm in pi v18 compound; do
    /tmp/v19-$arm-bin /tmp/v19-checker.json < "$F" >/tmp/v19-$arm-$T.out 2>/tmp/v19-$arm-$T.err
    cmp /tmp/v19-base-$T.out /tmp/v19-$arm-$T.out
  done
done
echo SEMANTIC_REPLAY=EXACT | tee /tmp/v19-semantic.txt

printf 'test,arm,instructions\n' >/tmp/v19-callgrind.csv
nix shell github:NixOS/nixpkgs/0ad6f47ea4fe188f4bc8f0380f93ae8523337c6c#valgrind -c bash -lc '
set -euo pipefail
cd /tmp/v19-arena
for spec in cedar-1m:/tmp/v19-cedar-1m.ndjson beta-ladder:_build/tests/perf/beta-ladder.ndjson grind-ring-5:_build/tests/perf/grind-ring-5.ndjson; do
 T=${spec%%:*}; F=${spec#*:}
 for arm in base pi v18 compound; do
  cf=/tmp/v19-$T-$arm.cg
  valgrind --tool=callgrind --callgrind-out-file="$cf" /tmp/v19-$arm-bin /tmp/v19-checker.json < "$F" >/dev/null 2>/tmp/v19-$T-$arm.vg
  ir=$(awk "/^summary:/ {print \$2; exit}" "$cf"); test -n "$ir"; printf "%s,%s,%s\n" "$T" "$arm" "$ir" >>/tmp/v19-callgrind.csv
 done
done'
python3 - <<'PY' | tee /tmp/v19-decision.txt
import csv,json
rows=list(csv.DictReader(open('/tmp/v19-callgrind.csv'))); d={(r['test'],r['arm']):int(r['instructions']) for r in rows}; out={}
for t in ('cedar-1m','beta-ladder','grind-ring-5'):
    b=d[(t,'base')]; out[t]={}
    for a in ('pi','v18','compound'):
        x=d[(t,a)]; q=(x/b-1)*100; out[t][a]=q; print(f'{t} {a}={x} vs_base={q:+.4f}%')
c=[out[t]['compound'] for t in out]
if max(c)<=.20 and min(c)<=-3: dec='COMPOUND_BIG_GAIN__ADVANCE_FULL_INCUMBENT_GATE'
elif max(c)<=.20 and min(c)<=-1: dec='COMPOUND_MATERIAL_GAIN__ADVANCE_FULL_INCUMBENT_GATE'
elif out['grind-ring-5']['compound']<out['grind-ring-5']['v18'] and max(c)<=.20: dec='COMPOUND_ADDITIVE__ADVANCE_FULL_INCUMBENT_GATE'
else: dec='NO_COMPOUND_PROMOTION__READ_RESIDUAL'
print('DECISION='+dec)
json.dump({'generation':'v19','semantic':'EXACT','deltas_pct':out,'decision':dec},open('/tmp/v19-generation.json','w'),indent=2)
PY
