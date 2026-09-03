#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])

# Add a sparse open-eval cache keyed by exactly the demanded value identities.
up=root/'src/util.rs'
s=up.read_text()
old="""    pub(crate) open_eval_cache: FxHashMap<(usize, ExprPtr<'t>), V<'a>>,
    pub(crate) open_eval_seen: FxHashSet<ExprPtr<'t>>,"""
new="""    pub(crate) open_eval_cache: FxHashMap<(usize, ExprPtr<'t>), V<'a>>,
    // v25: for sparse App demands, cache by the consequential values directly
    // instead of first materializing a projected environment.
    pub(crate) sparse_open_eval_cache: FxHashMap<(ExprPtr<'t>, u64, usize, usize, usize), V<'a>>,
    pub(crate) open_eval_seen: FxHashSet<ExprPtr<'t>>,"""
assert s.count(old)==1
s=s.replace(old,new,1)
old="""            open_eval_cache: session_fx_hash_map(),
            open_eval_seen: small_fx_hash_set(),"""
new="""            open_eval_cache: session_fx_hash_map(),
            sparse_open_eval_cache: session_fx_hash_map(),
            open_eval_seen: small_fx_hash_set(),"""
assert s.count(old)==1
s=s.replace(old,new,1)
old="""        self.open_eval_cache.clear();
        self.open_eval_seen.clear();"""
new="""        self.open_eval_cache.clear();
        self.sparse_open_eval_cache.clear();
        self.open_eval_seen.clear();"""
assert s.count(old)==1
s=s.replace(old,new,1)
old="""        shrink_map(&mut self.open_eval_cache);
        shrink_set(&mut self.open_eval_seen);"""
new="""        shrink_map(&mut self.open_eval_cache);
        shrink_map(&mut self.sparse_open_eval_cache);
        shrink_set(&mut self.open_eval_seen);"""
assert s.count(old)==1
s=s.replace(old,new,1)
up.write_text(s)

# Replace only the open-eval cache block. Sparse App terms with <=2 demanded
# variables use the demanded value pointers + mask + lsub identity as the key.
# On a miss they evaluate against the original env, so no projected frame is
# constructed merely to discover a miss. All other cases retain incumbent code.
ep=root/'src/eval.rs'
s=ep.read_text()
old="""        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {
            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {
                return *v;
            }
            let v = self.eval_no_cache(depth, te, e);
            self.tc_cache.open_eval_cache.insert(key, v);
            return v;
        }"""
new="""        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {
            // v25: App is the dominant open-eval producer. For one/two-variable
            // demands, the expression can only observe those selected values plus
            // the level substitution. Key that consequence directly and avoid
            // materializing a Framed projection just to perform cache lookup.
            if matches!(self.ctx.read_expr_ref(e), Expr::App { .. }) && e.num_loose_bvars() <= 64 {
                let mask = e.as_ref().fv_mask();
                let pc = mask.count_ones();
                if pc > 0 && pc <= 2 {
                    let mut bits = mask;
                    let i0 = bits.trailing_zeros() as u16;
                    bits &= bits - 1;
                    if let Some(v0) = env.lookup(i0) {
                        let p0 = v0 as *const Value<'t> as usize;
                        let mut p1 = 0usize;
                        let mut ok = true;
                        if bits != 0 {
                            let i1 = bits.trailing_zeros() as u16;
                            if let Some(v1) = env.lookup(i1) {
                                p1 = v1 as *const Value<'t> as usize;
                            } else {
                                ok = false;
                            }
                        }
                        if ok {
                            let lsub = env.lsub().map_or(0usize, |ls| ls as *const value::LevelSub<'t> as usize);
                            let key = (e, mask, p0, p1, lsub);
                            if let Some(v) = self.tc_cache.sparse_open_eval_cache.get(&key) {
                                return *v;
                            }
                            let v = self.eval_no_cache(depth, env, e);
                            self.tc_cache.sparse_open_eval_cache.insert(key, v);
                            return v;
                        }
                    }
                }
            }
            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {
                return *v;
            }
            let v = self.eval_no_cache(depth, te, e);
            self.tc_cache.open_eval_cache.insert(key, v);
            return v;
        }"""
assert s.count(old)==1, s.count(old)
s=s.replace(old,new,1)
ep.write_text(s)
print('V25_SPARSE_OPEN_EVAL_DEMAND_KEY_PATCH=APPLIED')
