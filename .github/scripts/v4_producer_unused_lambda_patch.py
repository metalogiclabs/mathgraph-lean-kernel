from pathlib import Path

# Add a per-session producer-side cache from original lambda bodies to an already-lowered
# representative. The expensive de Bruijn rewrite is paid when the lambda value is built,
# while application only performs an O(1) lookup and evaluates the precomputed representative.

u = Path('/tmp/cand/src/util.rs')
s = u.read_text()

old = "    pub(crate) lam_hc: FxHashMap<(ExprPtr<'t>, usize, ExprPtr<'t>), V<'a>>,\n"
new = old + "    pub(crate) unused_lam_body: FxHashMap<ExprPtr<'t>, ExprPtr<'t>>,\n"
assert s.count(old) == 1
s = s.replace(old, new, 1)

old = "            lam_hc: session_small_fx_hash_map(),\n"
new = old + "            unused_lam_body: session_small_fx_hash_map(),\n"
assert s.count(old) == 1
s = s.replace(old, new, 1)

old = "        self.lam_hc.clear();\n"
new = old + "        self.unused_lam_body.clear();\n"
assert s.count(old) >= 1
s = s.replace(old, new, 1)

u.write_text(s)

e = Path('/tmp/cand/src/eval.rs')
s = e.read_text()

old = """        debug_assert!(body.ctx.is_none());
        let key = (binder_type, body.env as *const value::Env<'t> as usize, body.body);
"""
new = """        debug_assert!(body.ctx.is_none());
        // Producer-side canonicalization: detect an unused binder and precompute the
        // de-Bruijn-correct representative once, when the lambda value is constructed.
        // Application below never lowers the body; it only selects this representative.
        if body.body.num_loose_bvars() <= 64 && (body.body.as_ref().fv_mask() & 1) == 0 {
            if !self.tc_cache.unused_lam_body.contains_key(&body.body) {
                let lowered = self.ctx.lower(body.body, 0, 1);
                self.tc_cache.unused_lam_body.insert(body.body, lowered);
            }
        }
        let key = (binder_type, body.env as *const value::Env<'t> as usize, body.body);
"""
assert s.count(old) == 1
s = s.replace(old, new, 1)

old1 = """            if let Value::Lam { body: clo, .. } = f {
                let a = if trivial { self.eval(depth, env, arg) } else { self.mk_thunk_hc(env, arg) };
                let clo_env = clo.env;
                let clo_body = clo.body;
                let new_env = value::env_extend(self.arena, clo_env, a);
                return self.eval(depth, new_env, clo_body);
            }
"""
new1 = """            if let Value::Lam { body: clo, .. } = f {
                let clo_env = clo.env;
                let clo_body = clo.body;
                if let Some(&lowered_body) = self.tc_cache.unused_lam_body.get(&clo_body) {
                    return self.eval(depth, clo_env, lowered_body);
                }
                let a = if trivial { self.eval(depth, env, arg) } else { self.mk_thunk_hc(env, arg) };
                let new_env = value::env_extend(self.arena, clo_env, a);
                return self.eval(depth, new_env, clo_body);
            }
"""
assert s.count(old1) == 1
s = s.replace(old1, new1, 1)

old2 = """            Value::Lam { body: clo, .. } => {
                let clo_env = clo.env;
                let clo_body = clo.body;
                let env = value::env_extend(self.arena, clo_env, a);
                self.eval(depth, env, clo_body)
            }
"""
new2 = """            Value::Lam { body: clo, .. } => {
                let clo_env = clo.env;
                let clo_body = clo.body;
                if let Some(&lowered_body) = self.tc_cache.unused_lam_body.get(&clo_body) {
                    return self.eval(depth, clo_env, lowered_body);
                }
                let env = value::env_extend(self.arena, clo_env, a);
                self.eval(depth, env, clo_body)
            }
"""
assert s.count(old2) == 1
s = s.replace(old2, new2, 1)

e.write_text(s)
