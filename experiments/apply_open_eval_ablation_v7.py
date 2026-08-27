from pathlib import Path
import sys

mode = sys.argv[1]
p = Path('src/eval.rs')
s = p.read_text()
old = '''        if matches!(
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
        }
'''
if mode == 'keep-key':
    new = '''        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {
            let te = self.key_env(env, e);
            return self.eval_no_cache(depth, te, e);
        }
'''
elif mode == 'bypass-key':
    new = '''        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {
            return self.eval_no_cache(depth, env, e);
        }
'''
else:
    raise SystemExit(f'unknown mode: {mode}')
assert old in s, 'open_eval block anchor not found'
p.write_text(s.replace(old, new, 1))
print(f'applied open_eval ablation v7 mode={mode}')
