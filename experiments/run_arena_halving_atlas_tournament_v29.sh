#!/usr/bin/env bash
set -euxo pipefail

# Reuse the exact v28 full-Mathlib/PGO verifier first. It leaves the arena export,
# base/incumbent binaries, configs and timings in /tmp for the atlas below.
bash experiments/run_arena_walltime_incumbent_v28.sh

MATHLIB=/tmp/v28-arena/_build/tests/mathlib.ndjson
INIT=/tmp/v28-arena/_build/tests/init-prelude.ndjson
BASESRC=/tmp/v28-base

# ---- Thread-scaling atlas on the verified Pi+v18 incumbent -------------------
for n in 1 2 4; do
  printf '%s\n' "{\"use_stdin\":true,\"nat_extension\":true,\"string_extension\":true,\"unpermitted_axiom_hard_error\":false,\"unsafe_permit_all_axioms\":true,\"num_threads\":$n,\"print_success_message\":false}" > "/tmp/v29-t${n}.json"
  /usr/bin/time -f '%e %U %S %M' -o "/tmp/v29-thread-${n}.time" /tmp/v28-inc-bin "/tmp/v29-t${n}.json" < "$MATHLIB" >/dev/null 2>"/tmp/v29-thread-${n}.err"
done

# ---- Parsing/materialization lower-bound probe -------------------------------
# parse_only is part of the export config. If the current Config schema accepts
# it at top level this gives a direct wall lower bound; otherwise record N/A and
# do not fail the scientific tournament.
printf '%s\n' '{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false,"parse_only":true}' >/tmp/v29-parse.json
set +e
/usr/bin/time -f '%e %U %S %M' -o /tmp/v29-parse.time /tmp/v28-inc-bin /tmp/v29-parse.json < "$MATHLIB" >/tmp/v29-parse.out 2>/tmp/v29-parse.err
PARSE_RC=$?
set -e

echo "V29_PARSE_ONLY_RC=$PARSE_RC" >/tmp/v29-atlas.txt
if [ "$PARSE_RC" -eq 0 ]; then cat /tmp/v29-parse.time >>/tmp/v29-atlas.txt; fi

# ---- Factorial candidate tournament: base / Pi-only / v18-only / compound ----
rm -rf /tmp/v29-pi /tmp/v29-v18 /tmp/v29-*-target /tmp/v29-pgo-*
cp -a "$BASESRC" /tmp/v29-pi
cp -a "$BASESRC" /tmp/v29-v18

python3 - <<'PY'
from pathlib import Path
pi_old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
pi_new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) {\n            return v;\n        }\n        if let Some(r) = self.store_lookup(depth, v) {"""
p=Path('/tmp/v29-pi/src/eval.rs'); s=p.read_text(); assert s.count(pi_old)==1; p.write_text(s.replace(pi_old,pi_new,1))

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
                        let v = if d < supplied { args[first_i + supplied - 1 - d] } else { clo.env.lookup((d - supplied) as u16).expect("v29 loose bvar") };
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
p=Path('/tmp/v29-v18/src/eval.rs'); s=p.read_text(); assert s.count(old)==1; p.write_text(s.replace(old,new,1))
print('V29_FACTORIAL_PATCHES=APPLIED')
PY

build_arm() {
  arm="$1"; src="/tmp/v29-$arm"; tgt="/tmp/v29-$arm-target"; pgo="/tmp/v29-pgo-$arm"
  rm -rf "$tgt" "$pgo"; mkdir -p "$pgo"
  (cd "$src" && CARGO_TARGET_DIR="$tgt" RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$pgo" cargo build --release --locked)
  "$tgt/release/sokonanoda" /tmp/v28-config.json < "$INIT" >/dev/null
  (cd /tmp/v28-arena && nix develop -c llvm-profdata merge -o "$pgo/merged.profdata" "$pgo")
  rm -rf "$tgt"
  (cd "$src" && CARGO_TARGET_DIR="$tgt" RUSTFLAGS="-C target-cpu=native -Cprofile-use=$pgo/merged.profdata" cargo build --release --locked)
  cp "$tgt/release/sokonanoda" "/tmp/v29-$arm-bin"
}
build_arm pi
build_arm v18

for arm in pi v18; do
  "/tmp/v29-$arm-bin" /tmp/v28-config.json < "$MATHLIB" >"/tmp/v29-$arm.out" 2>"/tmp/v29-$arm.err"
  cmp /tmp/v28-base.out "/tmp/v29-$arm.out"
  echo "V29_${arm^^}_SEMANTIC_REPLAY=EXACT"
done

# One matched tournament pass is enough to rank candidates cheaply; v28 already
# has three-run medians for base and compound. Alternate order to reduce drift.
/usr/bin/time -f '%e %U %S %M' -o /tmp/v29-pi.time /tmp/v29-pi-bin /tmp/v28-config.json < "$MATHLIB" >/dev/null 2>/tmp/v29-pi.measure.err
/usr/bin/time -f '%e %U %S %M' -o /tmp/v29-v18.time /tmp/v29-v18-bin /tmp/v28-config.json < "$MATHLIB" >/dev/null 2>/tmp/v29-v18.measure.err

python3 - <<'PY' | tee /tmp/v29-decision.txt
from pathlib import Path
import statistics

def row(path):
    e,u,s,r=Path(path).read_text().split(); return float(e),float(u)+float(s),int(r)
def v28(arm):
    xs=[]
    for i in range(1,4): xs.append(row(f'/tmp/v28-{arm}-{i}.time'))
    return statistics.median(x[0] for x in xs), statistics.median(x[1] for x in xs)
base_w,base_c=v28('base'); comp_w,comp_c=v28('inc')
pi_w,pi_c,_=row('/tmp/v29-pi.time'); v18_w,v18_c,_=row('/tmp/v29-v18.time')
threads={n:row(f'/tmp/v29-thread-{n}.time') for n in (1,2,4)}
print('V29_BASE_WALL_MEDIAN=%.3f'%base_w)
print('V29_PI_WALL=%.3f'%pi_w)
print('V29_V18_WALL=%.3f'%v18_w)
print('V29_COMPOUND_WALL_MEDIAN=%.3f'%comp_w)
for name,w in [('PI',pi_w),('V18',v18_w),('COMPOUND',comp_w)]: print(f'V29_{name}_VS_BASE_PCT={(w-base_w)/base_w*100:+.3f}')
for n,(w,c,r) in threads.items(): print(f'V29_THREADS_{n}_WALL={w:.3f} CPU={c:.3f} RSS_KB={r}')
print(f'V29_4THREAD_EFFECTIVE_CORES={threads[4][1]/threads[4][0]:.3f}')
print(f'V29_SAME_WORK_PERFECT_4CORE_FLOOR={threads[4][1]/4:.3f}')
print(f'V29_CPU_REDUCTION_NEEDED_FOR_2X_AT_4CORES={max(0,1-(base_w/2*4)/threads[4][1])*100:.3f}%')
parse=Path('/tmp/v29-parse.time')
if parse.exists() and Path('/tmp/v29-atlas.txt').read_text().splitlines()[0].endswith('=0'):
    pw,pc,pr=row('/tmp/v29-parse.time'); print(f'V29_PARSE_ONLY_WALL={pw:.3f} CPU={pc:.3f} RSS_KB={pr}')
else: print('V29_PARSE_ONLY_WALL=NA')
# winner is only a routing signal from this cheap factorial pass.
vals={'PI':pi_w,'V18':v18_w,'COMPOUND':comp_w}
winner=min(vals,key=vals.get)
print('V29_FACTORIAL_WINNER='+winner)
print('DECISION=V29_ROUTE_FROM_MEASURED_WALLTIME__NO_HOTSPOT_PROXY')
PY
