from pathlib import Path

p = Path('/tmp/cand/src/eval.rs')
s = p.read_text()

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
                if clo_body.num_loose_bvars() <= 64 && (clo_body.as_ref().fv_mask() & 1) == 0 {
                    // Binder 0 is observationally irrelevant, but outer de Bruijn
                    // references still need to shift when we omit the environment slot.
                    let lowered_body = self.ctx.lower(clo_body, 0, 1);
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
                if clo_body.num_loose_bvars() <= 64 && (clo_body.as_ref().fv_mask() & 1) == 0 {
                    let lowered_body = self.ctx.lower(clo_body, 0, 1);
                    return self.eval(depth, clo_env, lowered_body);
                }
                let env = value::env_extend(self.arena, clo_env, a);
                self.eval(depth, env, clo_body)
            }
"""
assert s.count(old2) == 1
s = s.replace(old2, new2, 1)

p.write_text(s)
