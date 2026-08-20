from pathlib import Path
import sys

root = Path(sys.argv[1])
mode = sys.argv[2]
assert mode in {"all", "apppi"}

up = root / "src/util.rs"
us = up.read_text()
old = "    pub(crate) open_eval_cache: FxHashMap<(usize, ExprPtr<'t>), V<'a>>,\n"
new = old + "    pub(crate) pre_open_eval_cache: FxHashMap<(usize, ExprPtr<'t>), V<'a>>,\n"
assert old in us
us = us.replace(old, new, 1)
old = "            open_eval_cache: session_fx_hash_map(),\n"
new = old + "            pre_open_eval_cache: session_fx_hash_map(),\n"
assert old in us
us = us.replace(old, new, 1)
up.write_text(us)

ep = root / "src/eval.rs"
es = ep.read_text()
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
if mode == "all":
    gate = "true"
else:
    gate = "matches!(self.ctx.read_expr_ref(e), Expr::App { .. } | Expr::Pi { .. })"
new = f'''        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App {{ .. }} | Expr::Proj {{ .. }} | Expr::Let {{ .. }} | Expr::Pi {{ .. }} | Expr::Lambda {{ .. }}
        ) {{
            // Conservative source-environment cache. This is exact: identical source
            // env pointer + expression implies identical key_env result and evaluation.
            // A hit avoids key_env/prune_env/frame materialization entirely.
            let use_pre = {gate};
            let pre_key = (env as *const value::Env<'t> as usize, e);
            if use_pre {{
                if let Some(v) = self.tc_cache.pre_open_eval_cache.get(&pre_key) {{
                    return v;
                }}
            }}
            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {{
                if use_pre {{ self.tc_cache.pre_open_eval_cache.insert(pre_key, v); }}
                return v;
            }}
            let v = self.eval_no_cache(depth, te, e);
            self.tc_cache.open_eval_cache.insert(key, v);
            if use_pre {{ self.tc_cache.pre_open_eval_cache.insert(pre_key, v); }}
            return v;
        }}
'''
assert old in es, "eval open-cache block changed"
es = es.replace(old, new, 1)
ep.write_text(es)
