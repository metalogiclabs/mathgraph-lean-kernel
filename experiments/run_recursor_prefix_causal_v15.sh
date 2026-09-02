#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
ARENA=f0fe3b379dbce91537417b529140d0ca250f271c
rm -rf /tmp/v15 /tmp/v15-arena /tmp/v15-target /tmp/v15-base-target
git worktree add /tmp/v15 "$BASE"
cd /tmp/v15
cargo test --locked
python3 - <<'PY'
from pathlib import Path
p=Path('src/eval.rs'); s=p.read_text()
s=s.replace('use std::cell::OnceCell;','use std::cell::OnceCell;\nuse std::sync::atomic::{AtomicU64, Ordering};',1)
anchor="pub(crate) type SpineArgs<'t> = smallvec::SmallVec<[V<'t>; 8]>;"
inject=r'''pub(crate) type SpineArgs<'t> = smallvec::SmallVec<[V<'t>; 8]>;
static V15_DOM_CALL:AtomicU64=AtomicU64::new(0);
static V15_HEAD_LAM:AtomicU64=AtomicU64::new(0);
static V15_HEAD_NONLAM:AtomicU64=AtomicU64::new(0);
static V15_INNER_LAM:AtomicU64=AtomicU64::new(0);
static V15_KEY_ENV:AtomicU64=AtomicU64::new(0);
static V15_FINAL_EVAL:AtomicU64=AtomicU64::new(0);
pub fn v15_report(){let g=|x:&AtomicU64|x.load(Ordering::Relaxed); eprintln!("V15_PREFIX dom_call={} head_lam={} head_nonlam={} inner_lam={} key_env={} final_eval={}",g(&V15_DOM_CALL),g(&V15_HEAD_LAM),g(&V15_HEAD_NONLAM),g(&V15_INNER_LAM),g(&V15_KEY_ENV),g(&V15_FINAL_EVAL));}'''
assert anchor in s; s=s.replace(anchor,inject,1)
fire_anchor="    fn fire_recursor(\n        &mut self, depth: u32,"
helpers=r'''    #[inline(never)]
    fn v15_key_env_phase(&mut self, env: E<'t>, e: ExprPtr<'t>) -> E<'t> {
        V15_KEY_ENV.fetch_add(1, Ordering::Relaxed);
        self.key_env(env, e)
    }

    #[inline(never)]
    fn v15_final_eval_phase(&mut self, depth: u32, env: E<'t>, body: ExprPtr<'t>) -> V<'t> {
        V15_FINAL_EVAL.fetch_add(1, Ordering::Relaxed);
        self.eval(depth, env, body)
    }

    #[inline(never)]
    fn v15_apply_dominant_prefix(&mut self, depth: u32, f0: V<'t>, args: &[V<'t>]) -> V<'t> {
        V15_DOM_CALL.fetch_add(1, Ordering::Relaxed);
        let mut f = f0;
        let mut i = 0usize;
        while i < args.len() {
            let Value::Lam { body: clo, .. } = f else {
                V15_HEAD_NONLAM.fetch_add(1, Ordering::Relaxed);
                f = self.apply(depth, f, args[i]);
                i += 1;
                continue
            };
            V15_HEAD_LAM.fetch_add(1, Ordering::Relaxed);
            let mut env = value::env_extend(self.arena, clo.env, args[i]);
            let mut body = clo.body;
            i += 1;
            while i < args.len() {
                let Expr::Lambda { body: inner, .. } = self.ctx.read_expr(body) else { break };
                V15_INNER_LAM.fetch_add(1, Ordering::Relaxed);
                let pruned = self.v15_key_env_phase(env, body);
                env = value::env_extend(self.arena, pruned, args[i]);
                body = inner;
                i += 1;
            }
            f = self.v15_final_eval_phase(depth, env, body);
        }
        f
    }

    fn fire_recursor(
        &mut self, depth: u32,'''
assert s.count(fire_anchor)==1; s=s.replace(fire_anchor,helpers,1)
old='''        result = self.apply_many(depth, result, &args[..nprefix]);
        result = self.apply_many(depth, result, &ctor_args[num_extra..]);
        result = self.apply_many(depth, result, &args[rec.major_idx() + 1..]);'''
new='''        let v15_dom = args.len() == 4
            && ctor_args.is_empty()
            && usize::from(rec_rule.ctor_telescope_size_wo_params) == 0
            && nprefix == 3
            && args.len().saturating_sub(rec.major_idx() + 1) == 0;
        result = if v15_dom {
            self.v15_apply_dominant_prefix(depth, result, &args[..nprefix])
        } else {
            self.apply_many(depth, result, &args[..nprefix])
        };
        result = self.apply_many(depth, result, &ctor_args[num_extra..]);
        result = self.apply_many(depth, result, &args[rec.major_idx() + 1..]);'''
assert old in s; s=s.replace(old,new,1)
p.write_text(s)

m=Path('src/main.rs'); t=m.read_text()
needle='    match out {'
assert t.count(needle)==1
t=t.replace(needle,'    sokonanoda::tc::v15_report();\n'+needle,1)
m.write_text(t)
PY
CARGO_TARGET_DIR=/tmp/v15-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked
cp /tmp/v15-target/release/sokonanoda /tmp/v15-probe-bin
printf '%s\n' '{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}' >/tmp/v15-checker.json
git clone https://github.com/leanprover/lean-kernel-arena /tmp/v15-arena
cd /tmp/v15-arena
git checkout "$ARENA"
for T in perf/app-lam perf/beta-ladder perf/let-ladder perf/grind-ring-5; do nix develop -c ./lka.py build-test "$T"; done
cd /tmp/v15
git checkout -- src/eval.rs src/main.rs
CARGO_TARGET_DIR=/tmp/v15-base-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked
cp /tmp/v15-base-target/release/sokonanoda /tmp/v15-base-bin
python3 - <<'PY'
import subprocess,re,json
arena='/tmp/v15-arena/_build/tests'; agg={}
for t in ['perf/app-lam','perf/beta-ladder','perf/let-ladder','perf/grind-ring-5']:
    inp=open(f'{arena}/{t}.ndjson','rb').read()
    b=subprocess.run(['/tmp/v15-base-bin','/tmp/v15-checker.json'],input=inp,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    a=subprocess.run(['/tmp/v15-probe-bin','/tmp/v15-checker.json'],input=inp,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    assert a.stdout==b.stdout,t
    lines=[x for x in a.stderr.decode(errors='replace').splitlines() if x.startswith('V15_PREFIX ')]
    if lines:
        d={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',lines[-1])}; agg[t]=d; print(t,d)
print('SEMANTIC_REPLAY=EXACT')
json.dump(agg,open('/tmp/v15-census.json','w'),indent=2)
g=agg.get('perf/grind-ring-5',{})
if not g or g.get('dom_call',0)==0: raise SystemExit('dominant group not observed')
if g['head_nonlam']==0 and g['head_lam']==g['dom_call'] and g['inner_lam']>=g['dom_call']:
    status='DOMINANT_PREFIX_IS_LAMBDA_CHAIN'
    grammar=['key_env demand mask','prune cache hit-vs-cold','final eval body shape']
else:
    status='MIXED_PREFIX_HEAD_FORMS'
    grammar=['head form transition','fallback apply cause','lambda-chain length']
res={'status':status,'grind':g,'next_grammar':grammar,'promotion':'NONE_MEASUREMENT_ONLY'}
json.dump(res,open('/tmp/v15-residual.json','w'),indent=2)
open('/tmp/v15-decision.txt','w').write('STATUS='+status+'\nNEXT_GRAMMAR='+','.join(grammar)+'\nDECISION=PROFILE_DOMINANT_PREFIX_INTERNAL_COST\nPROMOTION=NONE\n')
print('STATUS='+status); print('NEXT_GRAMMAR='+','.join(grammar))
PY
sudo apt-get update -qq
sudo apt-get install -y -qq valgrind
F=/tmp/v15-arena/_build/tests/perf/grind-ring-5.ndjson
valgrind --tool=callgrind --callgrind-out-file=/tmp/v15-callgrind.out /tmp/v15-probe-bin /tmp/v15-checker.json < "$F" >/dev/null 2>/tmp/v15-vg.txt
callgrind_annotate --inclusive=yes --auto=no /tmp/v15-callgrind.out > /tmp/v15-callgrind.txt
grep -E 'v15_apply_dominant_prefix|v15_key_env_phase|v15_final_eval_phase|prune_env_cold' /tmp/v15-callgrind.txt | head -100 | tee /tmp/v15-prefix-cost.txt
