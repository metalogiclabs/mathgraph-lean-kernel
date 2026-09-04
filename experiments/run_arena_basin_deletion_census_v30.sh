#!/usr/bin/env bash
set -euxo pipefail

BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v30-src /tmp/v30-arena /tmp/v30-target
git worktree add /tmp/v30-src "$BASE"

python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v30-src/src/eval.rs')
s=p.read_text()

# Promote the v29 factorial winner: Pi-only basin deletion.
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) {\n            return v;\n        }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert old in s
s=s.replace(old,new,1)

anchor='use std::collections::hash_map::Entry;\n'
probe=r'''use std::sync::atomic::{AtomicU64, Ordering};
static V30_EVAL: AtomicU64 = AtomicU64::new(0);
static V30_OPEN: AtomicU64 = AtomicU64::new(0);
static V30_OPEN_HIT: AtomicU64 = AtomicU64::new(0);
static V30_OPEN_MISS: AtomicU64 = AtomicU64::new(0);
static V30_KEY: AtomicU64 = AtomicU64::new(0);
static V30_PRUNE_COLD: AtomicU64 = AtomicU64::new(0);
static V30_NC_APP: AtomicU64 = AtomicU64::new(0);
static V30_NC_LAM: AtomicU64 = AtomicU64::new(0);
static V30_NC_PI: AtomicU64 = AtomicU64::new(0);
static V30_NC_LET: AtomicU64 = AtomicU64::new(0);
static V30_NC_PROJ: AtomicU64 = AtomicU64::new(0);
static V30_NC_VAR: AtomicU64 = AtomicU64::new(0);
static V30_NC_CONST: AtomicU64 = AtomicU64::new(0);
static V30_NC_SORT: AtomicU64 = AtomicU64::new(0);
static V30_FORCE: AtomicU64 = AtomicU64::new(0);
static V30_FORCE_PI: AtomicU64 = AtomicU64::new(0);
static V30_FORCE_LAM: AtomicU64 = AtomicU64::new(0);
static V30_FORCE_SORT: AtomicU64 = AtomicU64::new(0);
static V30_FORCE_RIGID: AtomicU64 = AtomicU64::new(0);
static V30_FORCE_UNFOLD: AtomicU64 = AtomicU64::new(0);
static V30_FORCE_THUNK: AtomicU64 = AtomicU64::new(0);

pub fn report_v30() {
    if std::env::var_os("MATHGRAPH_V30_CENSUS").is_none() { return; }
    eprintln!("V30 eval={} open={} open_hit={} open_miss={} key_env={} prune_cold={} nc_app={} nc_lam={} nc_pi={} nc_let={} nc_proj={} nc_var={} nc_const={} nc_sort={} force={} force_pi={} force_lam={} force_sort={} force_rigid={} force_unfold={} force_thunk={}",
      V30_EVAL.load(Ordering::Relaxed), V30_OPEN.load(Ordering::Relaxed), V30_OPEN_HIT.load(Ordering::Relaxed), V30_OPEN_MISS.load(Ordering::Relaxed),
      V30_KEY.load(Ordering::Relaxed), V30_PRUNE_COLD.load(Ordering::Relaxed), V30_NC_APP.load(Ordering::Relaxed), V30_NC_LAM.load(Ordering::Relaxed),
      V30_NC_PI.load(Ordering::Relaxed), V30_NC_LET.load(Ordering::Relaxed), V30_NC_PROJ.load(Ordering::Relaxed), V30_NC_VAR.load(Ordering::Relaxed),
      V30_NC_CONST.load(Ordering::Relaxed), V30_NC_SORT.load(Ordering::Relaxed), V30_FORCE.load(Ordering::Relaxed), V30_FORCE_PI.load(Ordering::Relaxed),
      V30_FORCE_LAM.load(Ordering::Relaxed), V30_FORCE_SORT.load(Ordering::Relaxed), V30_FORCE_RIGID.load(Ordering::Relaxed), V30_FORCE_UNFOLD.load(Ordering::Relaxed), V30_FORCE_THUNK.load(Ordering::Relaxed));
}
'''
assert anchor in s
s=s.replace(anchor,anchor+probe,1)

sig="""    pub(crate) fn eval(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {\n"""
assert sig in s
s=s.replace(sig,sig+'        V30_EVAL.fetch_add(1, Ordering::Relaxed);\n',1)

old2="""        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {
            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {
                return v;
            }
            let v = self.eval_no_cache(depth, te, e);
            self.tc_cache.open_eval_cache.insert(key, v);
            return v;
        }"""
new2="""        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {
            V30_OPEN.fetch_add(1, Ordering::Relaxed);
            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {
                V30_OPEN_HIT.fetch_add(1, Ordering::Relaxed);
                return v;
            }
            V30_OPEN_MISS.fetch_add(1, Ordering::Relaxed);
            let v = self.eval_no_cache(depth, te, e);
            self.tc_cache.open_eval_cache.insert(key, v);
            return v;
        }"""
assert old2 in s
s=s.replace(old2,new2,1)

ksig="""    pub(crate) fn key_env(&mut self, env: E<'t>, e: ExprPtr<'t>) -> E<'t> {\n"""
assert ksig in s
s=s.replace(ksig,ksig+'        V30_KEY.fetch_add(1, Ordering::Relaxed);\n',1)
old3='        self.prune_env_cold(e, mask, slot)\n'
assert old3 in s
s=s.replace(old3,'        V30_PRUNE_COLD.fetch_add(1, Ordering::Relaxed);\n'+old3,1)

nsig="""    fn eval_no_cache(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {\n        let first = *self.ctx.read_expr_ref(e);\n"""
assert nsig in s
nnew=nsig+'''        match first {\n            Expr::App { .. } => { V30_NC_APP.fetch_add(1, Ordering::Relaxed); }\n            Expr::Lambda { .. } => { V30_NC_LAM.fetch_add(1, Ordering::Relaxed); }\n            Expr::Pi { .. } => { V30_NC_PI.fetch_add(1, Ordering::Relaxed); }\n            Expr::Let { .. } => { V30_NC_LET.fetch_add(1, Ordering::Relaxed); }\n            Expr::Proj { .. } => { V30_NC_PROJ.fetch_add(1, Ordering::Relaxed); }\n            Expr::Var { .. } => { V30_NC_VAR.fetch_add(1, Ordering::Relaxed); }\n            Expr::Const { .. } => { V30_NC_CONST.fetch_add(1, Ordering::Relaxed); }\n            Expr::Sort { .. } => { V30_NC_SORT.fetch_add(1, Ordering::Relaxed); }\n            _ => {}\n        }\n'''
s=s.replace(nsig,nnew,1)

# Count the semantic constructor entering force_all before the Pi early-return.
fsig="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) {\n"""
assert fsig in s
fnew="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        V30_FORCE.fetch_add(1, Ordering::Relaxed);\n        match v {\n            Value::Pi { .. } => { V30_FORCE_PI.fetch_add(1, Ordering::Relaxed); }\n            Value::Lam { .. } => { V30_FORCE_LAM.fetch_add(1, Ordering::Relaxed); }\n            Value::Sort { .. } => { V30_FORCE_SORT.fetch_add(1, Ordering::Relaxed); }\n            Value::Rigid { .. } => { V30_FORCE_RIGID.fetch_add(1, Ordering::Relaxed); }\n            Value::Unfold { .. } => { V30_FORCE_UNFOLD.fetch_add(1, Ordering::Relaxed); }\n            Value::Thunk { .. } => { V30_FORCE_THUNK.fetch_add(1, Ordering::Relaxed); }\n            _ => {}\n        }\n        if matches!(v, Value::Pi { .. }) {\n"""
s=s.replace(fsig,fnew,1)
p.write_text(s)

p=Path('/tmp/v30-src/src/main.rs')
s=p.read_text()
old='''    // Pretty print as necessary\n    let pp_errs = export_file.pp_selected_declars(pp_destination.as_mut());'''
new='''    sokonanoda::eval::report_v30();\n    // Pretty print as necessary\n    let pp_errs = export_file.pp_selected_declars(pp_destination.as_mut());'''
assert old in s
p.write_text(s.replace(old,new,1))
print('V30_PI_PLUS_CENSUS_PATCH=APPLIED')
PY

cd /tmp/v30-src
cargo test --release --locked
RUSTFLAGS='-C target-cpu=native' cargo build --release --locked
cp target/release/sokonanoda /tmp/v30-bin
cat >/tmp/v30-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v30-arena
cd /tmp/v30-arena
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t"; done

: >/tmp/v30-census.txt
for t in std cedar mathlib; do
  echo "V30_TEST=$t" | tee -a /tmp/v30-census.txt
  MATHGRAPH_V30_CENSUS=1 /usr/bin/time -f 'V30_TIME wall=%e user=%U sys=%S rss=%M' /tmp/v30-bin /tmp/v30-config.json < "_build/tests/$t.ndjson" >/tmp/v30-$t.out 2>/tmp/v30-$t.err
  grep '^V30' /tmp/v30-$t.err | tee -a /tmp/v30-census.txt
done

python3 - <<'PY' | tee /tmp/v30-decision.txt
import re
from pathlib import Path
rows={}; cur=None
for line in Path('/tmp/v30-census.txt').read_text().splitlines():
    if line.startswith('V30_TEST='):
        cur=line.split('=',1)[1]; rows[cur]={}
    elif line.startswith('V30 '):
        for k,v in re.findall(r'(\w+)=(\d+)', line): rows[cur][k]=int(v)
for t,r in rows.items():
    op=r.get('open',0); hit=r.get('open_hit',0); miss=r.get('open_miss',0); force=r.get('force',0)
    print(f'{t}: open={op:,} hit={hit:,} miss={miss:,} hit_rate={(hit/op if op else 0):.2%} prune_cold={r.get("prune_cold",0):,}')
    print(f'{t}: no_cache app={r.get("nc_app",0):,} lam={r.get("nc_lam",0):,} pi={r.get("nc_pi",0):,} let={r.get("nc_let",0):,} proj={r.get("nc_proj",0):,}')
    print(f'{t}: force={force:,} pi={r.get("force_pi",0):,} lam={r.get("force_lam",0):,} sort={r.get("force_sort",0):,} rigid={r.get("force_rigid",0):,} unfold={r.get("force_unfold",0):,} thunk={r.get("force_thunk",0):,}')
m=rows.get('mathlib') or rows.get('cedar') or rows.get('std') or {}
force=max(1,m.get('force',0)); miss=max(1,m.get('open_miss',0))
# Consequence-first routing: rank classes by exposed repeated work, not by top-level function cost.
cands={
  'TERMINAL_FORCE_COLLAPSE_LAM_SORT': m.get('force_lam',0)+m.get('force_sort',0),
  'OPEN_EVAL_MISS_REPRESENTATION': m.get('open_miss',0),
  'APP_TRAJECTORY_COLLAPSE': m.get('nc_app',0),
  'PROJ_TRAJECTORY_COLLAPSE': m.get('nc_proj',0),
  'ENV_PROJECTION_DELETE': m.get('prune_cold',0),
}
print('V30_ROUTING_COUNTS='+repr(sorted(cands.items(), key=lambda kv: kv[1], reverse=True)))
winner=max(cands,key=cands.get)
print('V30_ROUTE='+winner)
print('V30_RULE=JOIN_BEFORE_OPTIMIZE__EXTRACT_CONSEQUENCE_BEFORE_IMPORTING_STRUCTURE')
print('V30_NEXT=build independent semantics-preserving candidate for winning basin; tournament on std+cedar before full Mathlib')
PY
