#!/usr/bin/env bash
set -euxo pipefail
V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
rm -rf /tmp/v2 /tmp/arena
git worktree add /tmp/v2 "$V2"
python3 - <<'PY'
from pathlib import Path

p=Path('/tmp/v2/src/eval.rs'); s=p.read_text()
anchor='use std::collections::hash_map::Entry;\n'
probe=r'''use std::sync::atomic::{AtomicU64, Ordering};
static MG_KEY_ENV_CALLS: AtomicU64 = AtomicU64::new(0);
static MG_KEY_ENV_CLOSED: AtomicU64 = AtomicU64::new(0);
static MG_KEY_ENV_WIDE: AtomicU64 = AtomicU64::new(0);
static MG_KEY_ENV_PROJECT: AtomicU64 = AtomicU64::new(0);
static MG_PRUNE_COLD: AtomicU64 = AtomicU64::new(0);
static MG_FORCE_ALL: AtomicU64 = AtomicU64::new(0);
static MG_IOTA_STEP: AtomicU64 = AtomicU64::new(0);
static MG_IOTA_VALUE: AtomicU64 = AtomicU64::new(0);
static MG_RECURSOR_IOTA: AtomicU64 = AtomicU64::new(0);
pub fn report_massive_gain_eval_census() {
    if std::env::var_os("MATHGRAPH_MASSIVE_CENSUS").is_none() { return; }
    eprintln!("MG_EVAL key_env_calls={} key_env_closed={} key_env_wide={} key_env_project={} prune_cold={} force_all={} iota_step={} iota_value={} recursor_iota={}",
        MG_KEY_ENV_CALLS.load(Ordering::Relaxed), MG_KEY_ENV_CLOSED.load(Ordering::Relaxed),
        MG_KEY_ENV_WIDE.load(Ordering::Relaxed), MG_KEY_ENV_PROJECT.load(Ordering::Relaxed),
        MG_PRUNE_COLD.load(Ordering::Relaxed), MG_FORCE_ALL.load(Ordering::Relaxed),
        MG_IOTA_STEP.load(Ordering::Relaxed), MG_IOTA_VALUE.load(Ordering::Relaxed),
        MG_RECURSOR_IOTA.load(Ordering::Relaxed));
}
'''
assert anchor in s; s=s.replace(anchor,anchor+probe,1)
old='''    #[inline]\n    pub(crate) fn key_env(&mut self, env: E<'t>, e: ExprPtr<'t>) -> E<'t> {\n        let k = e.num_loose_bvars();\n        if k == 0 {\n            return self.lsub_base(env.lsub());\n        }\n        if k > 64 {\n            return env;\n        }\n        self.prune_env(env, e.as_ref().fv_mask())\n    }'''
new='''    #[inline]\n    pub(crate) fn key_env(&mut self, env: E<'t>, e: ExprPtr<'t>) -> E<'t> {\n        MG_KEY_ENV_CALLS.fetch_add(1, Ordering::Relaxed);\n        let k = e.num_loose_bvars();\n        if k == 0 { MG_KEY_ENV_CLOSED.fetch_add(1, Ordering::Relaxed); return self.lsub_base(env.lsub()); }\n        if k > 64 { MG_KEY_ENV_WIDE.fetch_add(1, Ordering::Relaxed); return env; }\n        MG_KEY_ENV_PROJECT.fetch_add(1, Ordering::Relaxed);\n        self.prune_env(env, e.as_ref().fv_mask())\n    }'''
assert old in s; s=s.replace(old,new,1)
old='        self.prune_env_cold(e, mask, slot)\n'; assert old in s
s=s.replace(old,'        MG_PRUNE_COLD.fetch_add(1, Ordering::Relaxed);\n'+old,1)
for old,inc in [
("    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n",'        MG_FORCE_ALL.fetch_add(1, Ordering::Relaxed);\n'),
("    fn iota_step(&mut self, depth: u32, v: V<'t>) -> ForceStep<'t> {\n",'        MG_IOTA_STEP.fetch_add(1, Ordering::Relaxed);\n'),
("    pub(crate) fn iota_value(&mut self, depth: u32, v: V<'t>) -> Option<V<'t>> {\n",'        MG_IOTA_VALUE.fetch_add(1, Ordering::Relaxed);\n'),
("    fn do_recursor_iota(&mut self, depth: u32, name: NamePtr<'t>, levels: LevelsPtr<'t>, args: &[V<'t>]) -> Option<V<'t>> {\n",'        MG_RECURSOR_IOTA.fetch_add(1, Ordering::Relaxed);\n')]:
    assert old in s; s=s.replace(old,old+inc,1)
p.write_text(s)

p=Path('/tmp/v2/src/infer.rs'); s=p.read_text(); anchor='use InferFlag::*;\n'
probe=r'''use std::sync::atomic::{AtomicU64, Ordering};
static MG_INFER_CALLS: AtomicU64 = AtomicU64::new(0);
static MG_INFER_APP: AtomicU64 = AtomicU64::new(0);
static MG_INFER_LAMBDA: AtomicU64 = AtomicU64::new(0);
static MG_INFER_PI: AtomicU64 = AtomicU64::new(0);
static MG_INFER_LET: AtomicU64 = AtomicU64::new(0);
static MG_INFER_PROJ: AtomicU64 = AtomicU64::new(0);
static MG_TYPE_CACHE_HIT: AtomicU64 = AtomicU64::new(0);
static MG_TYPE_CACHE_MISS: AtomicU64 = AtomicU64::new(0);
static MG_BETA_FUSED: AtomicU64 = AtomicU64::new(0);
static MG_APP_GENERIC: AtomicU64 = AtomicU64::new(0);
pub fn report_massive_gain_infer_census() {
    if std::env::var_os("MATHGRAPH_MASSIVE_CENSUS").is_none() { return; }
    eprintln!("MG_INFER calls={} app={} lambda={} pi={} let={} proj={} cache_hit={} cache_miss={} beta_fused={} app_generic={}",
        MG_INFER_CALLS.load(Ordering::Relaxed), MG_INFER_APP.load(Ordering::Relaxed),
        MG_INFER_LAMBDA.load(Ordering::Relaxed), MG_INFER_PI.load(Ordering::Relaxed),
        MG_INFER_LET.load(Ordering::Relaxed), MG_INFER_PROJ.load(Ordering::Relaxed),
        MG_TYPE_CACHE_HIT.load(Ordering::Relaxed), MG_TYPE_CACHE_MISS.load(Ordering::Relaxed),
        MG_BETA_FUSED.load(Ordering::Relaxed), MG_APP_GENERIC.load(Ordering::Relaxed));
}
'''
assert anchor in s; s=s.replace(anchor,anchor+probe,1)
sig='''    pub(crate) fn infer_value(\n        &mut self,\n        flag: InferFlag,\n        depth: u32,\n        env: E<'t>,\n        ctx: C<'t>,\n        e: ExprPtr<'t>,\n    ) -> V<'t> {\n'''
body='''        MG_INFER_CALLS.fetch_add(1, Ordering::Relaxed);\n        match self.ctx.read_expr(e) {\n            App { .. } => { MG_INFER_APP.fetch_add(1, Ordering::Relaxed); }\n            Lambda { .. } => { MG_INFER_LAMBDA.fetch_add(1, Ordering::Relaxed); }\n            Pi { .. } => { MG_INFER_PI.fetch_add(1, Ordering::Relaxed); }\n            Let { .. } => { MG_INFER_LET.fetch_add(1, Ordering::Relaxed); }\n            Proj { .. } => { MG_INFER_PROJ.fetch_add(1, Ordering::Relaxed); }\n            _ => {}\n        }\n'''
assert sig in s; s=s.replace(sig,sig+body,1)
old='''        if let Some(cached) = self.tc_cache.type_cache.get(&key).copied() {\n            if flag == InferOnly || cached.checked_under == scope {\n                return cached.result;\n            }\n        }\n\n        let r = match self.ctx.read_expr(e) {'''
new='''        if let Some(cached) = self.tc_cache.type_cache.get(&key).copied() {\n            if flag == InferOnly || cached.checked_under == scope {\n                MG_TYPE_CACHE_HIT.fetch_add(1, Ordering::Relaxed);\n                return cached.result;\n            }\n        }\n        MG_TYPE_CACHE_MISS.fetch_add(1, Ordering::Relaxed);\n\n        let r = match self.ctx.read_expr(e) {'''
assert old in s; s=s.replace(old,new,1)
old='''            if let Lambda { binder_type, body, .. } = self.ctx.read_expr(fun) {\n                let dom = self.arg_value(depth, env, binder_type);'''
new='''            if let Lambda { binder_type, body, .. } = self.ctx.read_expr(fun) {\n                MG_BETA_FUSED.fetch_add(1, Ordering::Relaxed);\n                let dom = self.arg_value(depth, env, binder_type);'''
assert old in s; s=s.replace(old,new,1)
old='        let (fun, mut args) = self.ctx.unfold_apps_stack(self.arena, e);'; assert old in s
s=s.replace(old,'        MG_APP_GENERIC.fetch_add(1, Ordering::Relaxed);\n'+old,1)
p.write_text(s)

p=Path('/tmp/v2/src/main.rs'); s=p.read_text()
old='''    // Pretty print as necessary\n    let pp_errs = export_file.pp_selected_declars(pp_destination.as_mut());'''
new='''    sokonanoda::eval::report_massive_gain_eval_census();\n    sokonanoda::infer::report_massive_gain_infer_census();\n    // Pretty print as necessary\n    let pp_errs = export_file.pp_selected_declars(pp_destination.as_mut());'''
assert old in s; p.write_text(s.replace(old,new,1))
PY

cd /tmp/v2
cargo test --release --locked
RUSTFLAGS='-C target-cpu=x86-64' cargo build --release --locked
cp target/release/sokonanoda /tmp/v2-census
cat >/tmp/checker.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/arena
cd /tmp/arena
for t in init std mathlib; do nix develop -c ./lka.py build-test "$t"; done
: >/tmp/census.txt
for t in init std mathlib; do
  echo "MG_TEST $t" | tee -a /tmp/census.txt
  MATHGRAPH_MASSIVE_CENSUS=1 /usr/bin/time -v /tmp/v2-census /tmp/checker.json < "_build/tests/$t.ndjson" >/tmp/$t.out 2>/tmp/$t.err
  grep '^MG_' /tmp/$t.err | tee -a /tmp/census.txt
done
python3 - <<'PY' | tee /tmp/decision.txt
import re
from pathlib import Path
rows={}; cur=None
for line in Path('/tmp/census.txt').read_text().splitlines():
    if line.startswith('MG_TEST '): cur=line.split()[1]; rows[cur]={}
    elif line.startswith('MG_') and cur:
        for k,v in re.findall(r'(\w+)=(\d+)',line): rows[cur][k]=int(v)
for t,r in rows.items():
    kc=r.get('key_env_calls',0); cold=r.get('prune_cold',0); hit=r.get('cache_hit',0); miss=r.get('cache_miss',0); app=r.get('app',0); fused=r.get('beta_fused',0)
    print(f'{t}: key_env={kc:,} project={r.get("key_env_project",0):,} cold={cold:,} cold/key_env={(cold/kc if kc else 0):.3%}; infer={r.get("calls",0):,} cache_hit={hit:,} cache_miss={miss:,} hit_rate={(hit/(hit+miss) if hit+miss else 0):.3%}; apps={app:,} fused={fused:,} fused/app={(fused/app if app else 0):.3%}; force_all={r.get("force_all",0):,}; recursor_iota={r.get("recursor_iota",0):,}')
m=rows.get('mathlib') or rows.get('std') or rows.get('init') or {}
candidates=[('CANONICAL_ENV_IDENTITY',m.get('key_env_calls',0)+8*m.get('prune_cold',0)),('INFER_CACHE_POLICY',4*m.get('cache_miss',0)+m.get('cache_hit',0)),('FORCE_WHNF_PIPELINE',m.get('force_all',0)),('COMPILED_RECURSOR_PLANS',8*m.get('recursor_iota',0))]
candidates.sort(key=lambda x:x[1],reverse=True)
print('ROUTING_SCORES',candidates)
print('DECISION='+candidates[0][0])
print('NOTE=routing scores are event-weighted prioritization only; next separator must measure instructions and preserve semantics')
PY
