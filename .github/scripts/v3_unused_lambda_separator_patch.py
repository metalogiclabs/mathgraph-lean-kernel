from pathlib import Path

p = Path('/tmp/cand/src/eval.rs')
s = p.read_text()

a0 = s.index('            if let Value::Lam { body: clo, .. } = f {')
a1 = s.index('            let a = if trivial', a0)
a2 = s.index('            return self.apply(depth, f, a);', a1)
old = s[a0:a2]
assert 'let new_env = value::env_extend' in old
new = """            if let Value::Lam { body: clo, .. } = f {
                let clo_env = clo.env;
                let clo_body = clo.body;
                if crate::expr::ignores_binder(clo_body) {
                    return self.eval(depth, clo_env, clo_body);
                }
                let a = if trivial { self.eval(depth, env, arg) } else { self.mk_thunk_hc(env, arg) };
                let new_env = value::env_extend(self.arena, clo_env, a);
                return self.eval(depth, new_env, clo_body);
            }
"""
s = s[:a0] + new + s[a2:]

b0 = s.index('            Value::Lam { body: clo, .. } => {', s.index('pub(crate) fn apply('))
b1 = s.index('            Value::Rigid {', b0)
old2 = s[b0:b1]
assert 'value::env_extend' in old2
new2 = """            Value::Lam { body: clo, .. } => {
                let clo_env = clo.env;
                let clo_body = clo.body;
                if crate::expr::ignores_binder(clo_body) {
                    return self.eval(depth, clo_env, clo_body);
                }
                let env = value::env_extend(self.arena, clo_env, a);
                self.eval(depth, env, clo_body)
            }
"""
s = s[:b0] + new2 + s[b1:]
p.write_text(s)
