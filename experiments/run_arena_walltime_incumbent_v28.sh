#!/usr/bin/env bash
set -euxo pipefail

BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v28-base /tmp/v28-inc /tmp/v28-arena /tmp/v28-*-target /tmp/v28-pgo-*

git worktree add /tmp/v28-base "$BASE"
cp -a /tmp/v28-base /tmp/v28-inc

python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v28-inc/src/eval.rs'); s=p.read_text()
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
                        let v = if d < supplied { args[first_i + supplied - 1 - d] } else { clo.env.lookup((d - supplied) as u16).expect("v28 loose bvar") };
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
assert s.count(old)==1
s=s.replace(pi_old,pi_new,1).replace(old,new,1)
p.write_text(s)
print('V28_PI_PLUS_V18_PATCH=APPLIED')
PY

printf '%s\n' '{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}' >/tmp/v28-config.json

git clone https://github.com/leanprover/lean-kernel-arena /tmp/v28-arena
cd /tmp/v28-arena
ARENA_SHA=$(git rev-parse HEAD)
echo "ARENA_SHA=$ARENA_SHA" | tee /tmp/v28-provenance.txt
nix develop -c ./lka.py build-test init-prelude mathlib
INIT=/tmp/v28-arena/_build/tests/init-prelude.ndjson
MATHLIB=/tmp/v28-arena/_build/tests/mathlib.ndjson

auto_build() {
  arm="$1"
  src="/tmp/v28-$arm"
  tgt="/tmp/v28-$arm-target"
  pgo="/tmp/v28-pgo-$arm"
  rm -rf "$tgt" "$pgo"
  mkdir -p "$pgo"
  (cd "$src" && CARGO_TARGET_DIR="$tgt" RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$pgo" cargo build --release --locked)
  "$tgt/release/sokonanoda" /tmp/v28-config.json < "$INIT" >/dev/null
  llvm-profdata merge -o "$pgo/merged.profdata" "$pgo"
  rm -rf "$tgt"
  (cd "$src" && CARGO_TARGET_DIR="$tgt" RUSTFLAGS="-C target-cpu=native -Cprofile-use=$pgo/merged.profdata" cargo build --release --locked)
  cp "$tgt/release/sokonanoda" "/tmp/v28-$arm-bin"
}

auto_build base
auto_build inc

# Correctness gate on the exact Arena Mathlib export.
/tmp/v28-base-bin /tmp/v28-config.json < "$MATHLIB" >/tmp/v28-base.out 2>/tmp/v28-base.err
/tmp/v28-inc-bin /tmp/v28-config.json < "$MATHLIB" >/tmp/v28-inc.out 2>/tmp/v28-inc.err
cmp /tmp/v28-base.out /tmp/v28-inc.out
echo V28_MATHLIB_SEMANTIC_REPLAY=EXACT | tee /tmp/v28-semantic.txt

# One unmeasured warm-up per arm, then six matched alternating runs: AB BA AB.
/tmp/v28-base-bin /tmp/v28-config.json < "$MATHLIB" >/dev/null 2>/dev/null
/tmp/v28-inc-bin /tmp/v28-config.json < "$MATHLIB" >/dev/null 2>/dev/null

measure() {
  arm="$1"; idx="$2"
  /usr/bin/time -f '%e %U %S %M' -o "/tmp/v28-${arm}-${idx}.time" "/tmp/v28-${arm}-bin" /tmp/v28-config.json < "$MATHLIB" >/dev/null 2>"/tmp/v28-${arm}-${idx}.err"
}
measure base 1
measure inc 1
measure inc 2
measure base 2
measure base 3
measure inc 3

python3 - <<'PY' | tee /tmp/v28-decision.txt
from pathlib import Path
import statistics

def vals(arm):
    rows=[]
    for i in range(1,4):
        e,u,s,r=Path(f'/tmp/v28-{arm}-{i}.time').read_text().split()
        rows.append((float(e),float(u),float(s),int(r)))
    return rows
b=vals('base'); c=vals('inc')
bw=[x[0] for x in b]; cw=[x[0] for x in c]
bm=statistics.median(bw); cm=statistics.median(cw)
d=(cm-bm)/bm*100
print('V28_MATHLIB_SEMANTIC_REPLAY=EXACT')
print('BASE_WALL_RUNS='+','.join(f'{x:.3f}' for x in bw))
print('INCUMBENT_WALL_RUNS='+','.join(f'{x:.3f}' for x in cw))
print(f'BASE_WALL_MEDIAN={bm:.3f}')
print(f'INCUMBENT_WALL_MEDIAN={cm:.3f}')
print(f'INCUMBENT_VS_SUBMITTED_WALL_PCT={d:+.3f}')
print('BASE_CPU_RUNS='+','.join(f'{x[1]+x[2]:.3f}' for x in b))
print('INCUMBENT_CPU_RUNS='+','.join(f'{x[1]+x[2]:.3f}' for x in c))
print('BASE_MAXRSS_KB='+','.join(str(x[3]) for x in b))
print('INCUMBENT_MAXRSS_KB='+','.join(str(x[3]) for x in c))
if d <= -2.0:
    dec='V28_CLEAR_WALLTIME_WIN__PREPARE_ARENA_SUBMISSION'
elif d <= -0.5:
    dec='V28_SMALL_WALLTIME_WIN__REPEAT_FULL_MATHLIB_GATE'
elif d < 0:
    dec='V28_WEAK_WALLTIME_WIN__DO_NOT_SUBMIT_YET'
else:
    dec='V28_NO_WALLTIME_GAIN__KEEP_CURRENT_ARENA_REVISION'
print('DECISION='+dec)
PY
