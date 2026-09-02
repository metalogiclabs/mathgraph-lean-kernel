#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
ARENA=f0fe3b379dbce91537417b529140d0ca250f271c
rm -rf /tmp/v18-base /tmp/v18-v17 /tmp/v18-v18 /tmp/v18-arena /tmp/v18-*-target

git worktree add /tmp/v18-base "$BASE"
cp -a /tmp/v18-base /tmp/v18-v17
cp -a /tmp/v18-base /tmp/v18-v18

python3 - <<'PY'
from pathlib import Path
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
v17='''    pub(crate) fn apply_many(&mut self, depth: u32, f0: V<'t>, args: &[V<'t>]) -> V<'t> {
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
                        let mut direct_env = env;
                        let mut direct_body = body;
                        let mut direct_i = i;
                        while direct_i < args.len() {
                            let Expr::Lambda { body: inner, .. } = self.ctx.read_expr(direct_body) else { unreachable!() };
                            direct_env = value::env_extend(self.arena, direct_env, args[direct_i]);
                            direct_body = inner;
                            direct_i += 1;
                        }
                        let v = direct_env.lookup(dbj_idx).expect("apply_many v17: loose bvar");
                        f = self.force_thunk(depth, v);
                        i = direct_i;
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
v18='''    pub(crate) fn apply_many(&mut self, depth: u32, f0: V<'t>, args: &[V<'t>]) -> V<'t> {
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
                            clo.env.lookup((d - supplied) as u32).expect("apply_many v18: loose bvar")
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
for arm,new in [('v17',v17),('v18',v18)]:
    p=Path(f'/tmp/v18-{arm}/src/eval.rs'); s=p.read_text(); assert s.count(old)==1, (arm,s.count(old)); p.write_text(s.replace(old,new,1))
print('V18_PATCHES=APPLIED')
PY

for arm in base v17 v18; do
  (cd /tmp/v18-$arm && cargo test --locked)
  (cd /tmp/v18-$arm && CARGO_TARGET_DIR=/tmp/v18-$arm-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked)
  cp /tmp/v18-$arm-target/release/sokonanoda /tmp/v18-$arm-bin
done

printf '%s\n' '{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}' >/tmp/v18-checker.json

git clone https://github.com/leanprover/lean-kernel-arena /tmp/v18-arena
cd /tmp/v18-arena
git checkout "$ARENA"
nix develop -c ./lka.py build-test std
for T in perf/app-lam perf/beta-ladder perf/let-ladder perf/grind-ring-5; do nix develop -c ./lka.py build-test "$T"; done

for spec in std:_build/tests/std.ndjson app-lam:_build/tests/perf/app-lam.ndjson beta-ladder:_build/tests/perf/beta-ladder.ndjson let-ladder:_build/tests/perf/let-ladder.ndjson grind-ring-5:_build/tests/perf/grind-ring-5.ndjson; do
  T=${spec%%:*}; F=${spec#*:}
  /tmp/v18-base-bin /tmp/v18-checker.json < "$F" > /tmp/v18-base-$T.out 2>/tmp/v18-base-$T.err
  for arm in v17 v18; do
    /tmp/v18-$arm-bin /tmp/v18-checker.json < "$F" > /tmp/v18-$arm-$T.out 2>/tmp/v18-$arm-$T.err
    cmp /tmp/v18-base-$T.out /tmp/v18-$arm-$T.out
  done
done
echo SEMANTIC_REPLAY=EXACT | tee /tmp/v18-semantic.txt

head -n 1000000 _build/tests/std.ndjson >/tmp/v18-std-1m.ndjson
printf 'test,arm,instructions\n' >/tmp/v18-callgrind.csv
nix shell github:NixOS/nixpkgs/0ad6f47ea4fe188f4bc8f0380f93ae8523337c6c#valgrind -c bash -lc '
set -euo pipefail
cd /tmp/v18-arena
for spec in std-1m:/tmp/v18-std-1m.ndjson app-lam:_build/tests/perf/app-lam.ndjson beta-ladder:_build/tests/perf/beta-ladder.ndjson grind-ring-5:_build/tests/perf/grind-ring-5.ndjson; do
 T=${spec%%:*}; F=${spec#*:}
 for arm in base v17 v18; do
  cf=/tmp/v18-$T-$arm.cg
  valgrind --tool=callgrind --callgrind-out-file="$cf" /tmp/v18-$arm-bin /tmp/v18-checker.json < "$F" >/dev/null 2>/tmp/v18-$T-$arm.vg
  ir=$(awk "/^summary:/ {print \$2; exit}" "$cf"); test -n "$ir"; printf "%s,%s,%s\n" "$T" "$arm" "$ir" >>/tmp/v18-callgrind.csv
 done
done
'
python3 - <<'PY' | tee /tmp/v18-decision.txt
import csv,json
rows=list(csv.DictReader(open('/tmp/v18-callgrind.csv'))); d={(r['test'],r['arm']):int(r['instructions']) for r in rows}; out={}
for t in ('std-1m','app-lam','beta-ladder','grind-ring-5'):
 b=d[(t,'base')]; a=d[(t,'v17')]; c=d[(t,'v18')]
 db=(c/b-1)*100; dv=(c/a-1)*100
 out[t]={'base':b,'v17':a,'v18':c,'v18_vs_base_pct':db,'v18_vs_v17_pct':dv}
 print(f'{t} base={b} v17={a} v18={c} v18_vs_base={db:+.4f}% v18_vs_v17={dv:+.4f}%')
worst=max(x['v18_vs_base_pct'] for x in out.values()); grind=out['grind-ring-5']
if grind['v18_vs_v17_pct'] < 0 and grind['v18_vs_base_pct'] < 0 and worst <= .20: dec='V18_WINS_LOCAL_TOURNAMENT__RUN_CEDAR_INCUMBENT_GATE'
elif grind['v18_vs_base_pct'] < 0 and worst <= .20: dec='V17_REMAINS_LOCAL_INCUMBENT__RETAIN_V18_ALTERNATE'
else: dec='KILL_V18__V17_REMAINS_LOCAL_INCUMBENT'
print('DECISION='+dec)
json.dump({'generation_id':'v18','incumbent_workflow':'v17 weak-positive local incumbent','residual_before':'v17 still allocates intermediate env nodes before terminal Var lookup','candidate_actions':['DIRECT_DEBRUIJN_PROJECTION','retain v17'],'selected_action':'DIRECT_DEBRUIJN_PROJECTION','directness_class':'PUSH','verifier':'exact stdout replay std + four perf; deterministic Callgrind','semantic_replay':'EXACT','results':out,'promotion_decision':dec,'residual_after':'Cedar/full incumbent gate only if v18 wins; otherwise preserve v17'},open('/tmp/v18-generation.json','w'),indent=2)
PY
