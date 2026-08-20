#!/usr/bin/env bash
set -euxo pipefail
V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
rm -rf /tmp/v2-cacheecon /tmp/arena-cacheecon /tmp/cache-econ
mkdir -p /tmp/cache-econ
git worktree add /tmp/v2-cacheecon "$V2"
git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/arena-cacheecon
cd /tmp/arena-cacheecon
for t in init std mathlib; do nix develop -c ./lka.py build-test "$t"; done
cd /tmp/v2-cacheecon
python3 - <<'PY'
from pathlib import Path
p=Path('src/eval.rs'); s=p.read_text()
anchor='use std::collections::hash_map::Entry;\n'
probe=r'''use std::sync::atomic::{AtomicU64, Ordering};
static MG_OPEN_CALL: AtomicU64 = AtomicU64::new(0);
static MG_OPEN_HIT: AtomicU64 = AtomicU64::new(0);
static MG_OPEN_MISS: AtomicU64 = AtomicU64::new(0);
static MG_KIND_CALL: [AtomicU64; 5] = [const { AtomicU64::new(0) }; 5];
static MG_KIND_HIT: [AtomicU64; 5] = [const { AtomicU64::new(0) }; 5];
static MG_KIND_MISS: [AtomicU64; 5] = [const { AtomicU64::new(0) }; 5];
static MG_KEY_ENV: AtomicU64 = AtomicU64::new(0);
static MG_PRUNE_CALL: AtomicU64 = AtomicU64::new(0);
static MG_PRUNE_COLD: AtomicU64 = AtomicU64::new(0);
fn mg_kind(e: &Expr<'_>) -> usize { match e { Expr::App {..}=>0, Expr::Proj {..}=>1, Expr::Let {..}=>2, Expr::Pi {..}=>3, Expr::Lambda {..}=>4, _=>4 } }
pub fn report_eval_cache_stats() {
    if std::env::var_os("MATHGRAPH_CACHE_ECON").is_none() { return }
    eprintln!("MG_CACHE open_calls={} open_hits={} open_misses={} key_env={} prune_calls={} prune_cold={} app_calls={} app_hits={} app_misses={} proj_calls={} proj_hits={} proj_misses={} let_calls={} let_hits={} let_misses={} pi_calls={} pi_hits={} pi_misses={} lam_calls={} lam_hits={} lam_misses={}",
      MG_OPEN_CALL.load(Ordering::Relaxed),MG_OPEN_HIT.load(Ordering::Relaxed),MG_OPEN_MISS.load(Ordering::Relaxed),MG_KEY_ENV.load(Ordering::Relaxed),MG_PRUNE_CALL.load(Ordering::Relaxed),MG_PRUNE_COLD.load(Ordering::Relaxed),
      MG_KIND_CALL[0].load(Ordering::Relaxed),MG_KIND_HIT[0].load(Ordering::Relaxed),MG_KIND_MISS[0].load(Ordering::Relaxed),
      MG_KIND_CALL[1].load(Ordering::Relaxed),MG_KIND_HIT[1].load(Ordering::Relaxed),MG_KIND_MISS[1].load(Ordering::Relaxed),
      MG_KIND_CALL[2].load(Ordering::Relaxed),MG_KIND_HIT[2].load(Ordering::Relaxed),MG_KIND_MISS[2].load(Ordering::Relaxed),
      MG_KIND_CALL[3].load(Ordering::Relaxed),MG_KIND_HIT[3].load(Ordering::Relaxed),MG_KIND_MISS[3].load(Ordering::Relaxed),
      MG_KIND_CALL[4].load(Ordering::Relaxed),MG_KIND_HIT[4].load(Ordering::Relaxed),MG_KIND_MISS[4].load(Ordering::Relaxed));
}
'''
assert anchor in s; s=s.replace(anchor,anchor+probe,1)
s=s.replace("    fn prune_env(&mut self, e: E<'t>, mask: u64) -> E<'t> {\n", "    fn prune_env(&mut self, e: E<'t>, mask: u64) -> E<'t> {\n        MG_PRUNE_CALL.fetch_add(1, Ordering::Relaxed);\n",1)
s=s.replace("        self.prune_env_cold(e, mask, slot)\n", "        MG_PRUNE_COLD.fetch_add(1, Ordering::Relaxed);\n        self.prune_env_cold(e, mask, slot)\n",1)
s=s.replace("    pub(crate) fn key_env(&mut self, env: E<'t>, e: ExprPtr<'t>) -> E<'t> {\n", "    pub(crate) fn key_env(&mut self, env: E<'t>, e: ExprPtr<'t>) -> E<'t> {\n        MG_KEY_ENV.fetch_add(1, Ordering::Relaxed);\n",1)
old='''        if matches!(\n            self.ctx.read_expr_ref(e),\n            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }\n        ) {\n            let te = self.key_env(env, e);\n            let key = (te as *const value::Env<'t> as usize, e);\n            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {\n                return v;\n            }\n            let v = self.eval_no_cache(depth, te, e);\n            self.tc_cache.open_eval_cache.insert(key, v);\n            return v;\n        }'''
new='''        if matches!(\n            self.ctx.read_expr_ref(e),\n            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }\n        ) {\n            let kind = mg_kind(self.ctx.read_expr_ref(e));\n            MG_OPEN_CALL.fetch_add(1, Ordering::Relaxed); MG_KIND_CALL[kind].fetch_add(1, Ordering::Relaxed);\n            let te = self.key_env(env, e);\n            let key = (te as *const value::Env<'t> as usize, e);\n            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {\n                MG_OPEN_HIT.fetch_add(1, Ordering::Relaxed); MG_KIND_HIT[kind].fetch_add(1, Ordering::Relaxed);\n                return v;\n            }\n            MG_OPEN_MISS.fetch_add(1, Ordering::Relaxed); MG_KIND_MISS[kind].fetch_add(1, Ordering::Relaxed);\n            let v = self.eval_no_cache(depth, te, e);\n            self.tc_cache.open_eval_cache.insert(key, v);\n            return v;\n        }'''
assert old in s; s=s.replace(old,new,1); p.write_text(s)
m=Path('src/main.rs'); t=m.read_text(); a='    export_file.check_all_declars();\n'; assert a in t; t=t.replace(a,a+'    sokonanoda::eval::report_eval_cache_stats();\n',1); m.write_text(t)
PY
cargo test --release --locked
RUSTFLAGS='-C target-cpu=native' cargo build --release --locked
cp target/release/sokonanoda /tmp/cache-econ/checker
cat >/tmp/cache-econ/checker.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}
EOF
for t in init std mathlib; do
  MATHGRAPH_CACHE_ECON=1 /tmp/cache-econ/checker /tmp/cache-econ/checker.json < /tmp/arena-cacheecon/_build/tests/$t.ndjson >/tmp/cache-econ/$t.out 2>/tmp/cache-econ/$t.err
  grep '^MG_CACHE ' /tmp/cache-econ/$t.err | tail -1 | tee /tmp/cache-econ/$t.stats
done
python3 - <<'PY' | tee /tmp/cache-econ/summary.txt
from pathlib import Path
for test in ['init','std','mathlib']:
    xs=Path(f'/tmp/cache-econ/{test}.stats').read_text().split()[1:]
    d={k:int(v) for k,v in (x.split('=',1) for x in xs)}
    print('\nTEST',test)
    print('open_hit_rate', d['open_hits']/max(d['open_calls'],1))
    print('cold_prune_per_open', d['prune_cold']/max(d['open_calls'],1))
    for k in ['app','proj','let','pi','lam']:
        calls=d[k+'_calls']; hits=d[k+'_hits']; misses=d[k+'_misses']
        print(k,'calls',calls,'hit_rate',hits/max(calls,1),'misses',misses)
print('\nDECISION: select high-volume low-hit class for selective cache-bypass A/B only if it is consistent on std+mathlib; otherwise optimize prune reconstruction itself.')
PY
