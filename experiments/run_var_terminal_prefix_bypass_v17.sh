#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
ARENA=f0fe3b379dbce91537417b529140d0ca250f271c
rm -rf /tmp/v17-base /tmp/v17-candidate /tmp/v17-arena /tmp/v17-base-target /tmp/v17-candidate-target

git worktree add /tmp/v17-base "$BASE"
cp -a /tmp/v17-base /tmp/v17-candidate

python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v17-candidate/src/eval.rs')
s=p.read_text()
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
            let mut env = value::env_extend(self.arena, clo.env, args[i]);
            let mut body = clo.body;
            i += 1;

            // v17: v16 found the dominant recursor-prefix basin has exactly two
            // remaining lambda arguments and a terminal Var body, while key_env
            // pruning dominates its cost.  In that structurally certified shape,
            // keeping the unpruned environment is a semantic superset: extend the
            // same bindings and perform the final variable lookup directly.
            // All other shapes retain the incumbent key_env path unchanged.
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
assert s.count(old)==1, s.count(old)
p.write_text(s.replace(old,new,1))
print('V17_PATCH=APPLIED')
PY

for arm in base candidate; do
  (cd /tmp/v17-$arm && cargo test --locked)
  (cd /tmp/v17-$arm && CARGO_TARGET_DIR=/tmp/v17-$arm-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked)
  cp /tmp/v17-$arm-target/release/sokonanoda /tmp/v17-$arm-bin
done

printf '%s\n' '{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}' >/tmp/v17-checker.json

git clone https://github.com/leanprover/lean-kernel-arena /tmp/v17-arena
cd /tmp/v17-arena
git checkout "$ARENA"
nix develop -c ./lka.py build-test std
for T in perf/app-lam perf/beta-ladder perf/let-ladder perf/grind-ring-5; do
  nix develop -c ./lka.py build-test "$T"
done

for spec in \
  std:_build/tests/std.ndjson \
  app-lam:_build/tests/perf/app-lam.ndjson \
  beta-ladder:_build/tests/perf/beta-ladder.ndjson \
  let-ladder:_build/tests/perf/let-ladder.ndjson \
  grind-ring-5:_build/tests/perf/grind-ring-5.ndjson; do
  T=${spec%%:*}; F=${spec#*:}
  /tmp/v17-base-bin /tmp/v17-checker.json < "$F" > "/tmp/v17-base-$T.out" 2> "/tmp/v17-base-$T.err"
  /tmp/v17-candidate-bin /tmp/v17-checker.json < "$F" > "/tmp/v17-candidate-$T.out" 2> "/tmp/v17-candidate-$T.err"
  cmp "/tmp/v17-base-$T.out" "/tmp/v17-candidate-$T.out"
done
echo SEMANTIC_REPLAY=EXACT | tee /tmp/v17-semantic.txt

head -n 1000000 _build/tests/std.ndjson >/tmp/v17-std-1m.ndjson
printf 'test,arm,instructions\n' >/tmp/v17-callgrind.csv
nix shell github:NixOS/nixpkgs/0ad6f47ea4fe188f4bc8f0380f93ae8523337c6c#valgrind -c bash -lc '
  set -euo pipefail
  cd /tmp/v17-arena
  for spec in std-1m:/tmp/v17-std-1m.ndjson app-lam:_build/tests/perf/app-lam.ndjson beta-ladder:_build/tests/perf/beta-ladder.ndjson grind-ring-5:_build/tests/perf/grind-ring-5.ndjson; do
    T=${spec%%:*}; F=${spec#*:}
    for arm in base candidate; do
      cf="/tmp/v17-$T-$arm.cg"
      valgrind --tool=callgrind --callgrind-out-file="$cf" "/tmp/v17-$arm-bin" /tmp/v17-checker.json < "$F" >/dev/null 2>"/tmp/v17-$T-$arm.vg"
      ir=$(awk "/^summary:/ {print \$2; exit}" "$cf")
      test -n "$ir"
      printf "%s,%s,%s\n" "$T" "$arm" "$ir" >>/tmp/v17-callgrind.csv
    done
  done
'

python3 - <<'PY' | tee /tmp/v17-decision.txt
import csv, json
rows=list(csv.DictReader(open('/tmp/v17-callgrind.csv')))
d={(r['test'],r['arm']):int(r['instructions']) for r in rows}
out={}
for t in ('std-1m','app-lam','beta-ladder','grind-ring-5'):
    b=d[(t,'base')]; c=d[(t,'candidate')]; delta=(c/b-1)*100
    out[t]={'base':b,'candidate':c,'delta_pct':delta}
    print(f'{t} base={b} candidate={c} delta={delta:+.4f}%')
worst=max(x['delta_pct'] for x in out.values())
grind=out['grind-ring-5']['delta_pct']
if grind <= -5.0 and worst <= 0.20:
    decision='KEEP_MAJOR__RUN_FULL_CEDAR_AND_INCREMENTAL_INCUMBENT_GATE'
elif grind <= -1.0 and worst <= 0.20:
    decision='KEEP__RUN_FULL_CEDAR_AND_INCREMENTAL_INCUMBENT_GATE'
elif grind < 0 and worst <= 0.20:
    decision='WEAK_POSITIVE__RETAIN_AND_COMPARE_NEXT_PORTFOLIO_CHALLENGER'
else:
    decision='KILL__FALL_THROUGH_TO_NEXT_PORTFOLIO_CANDIDATE'
print('DECISION='+decision)
record={
 'generation_id':'v17',
 'residual_before':'dominant recursor prefix: repeated expr, fresh Cons env, support popcount 1-2, terminal Var',
 'selected_action':'VAR_TERMINAL_PREFIX_BYPASS',
 'directness_class':'PUSH',
 'prior_killed_action':'C_SMALL4 generic one-bit prune traversal (+1.908% grind-ring-5)',
 'verifier':'exact stdout replay on std + four frozen perf workloads; deterministic Callgrind',
 'semantic_replay':'EXACT',
 'results':out,
 'promotion_decision':decision,
 'residual_after':'pending full Cedar/incremental incumbent gate if positive; otherwise next v16 portfolio candidate'
}
json.dump(record,open('/tmp/v17-generation.json','w'),indent=2)
PY
