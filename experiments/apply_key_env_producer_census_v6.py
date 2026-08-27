from pathlib import Path

p = Path('src/eval.rs')
s = p.read_text()
needle = "use std::collections::hash_map::Entry;\n"
insert = """use std::collections::hash_map::Entry;\nuse std::sync::atomic::{AtomicU64, Ordering};\n\nstatic KEY_ENV_THUNK: AtomicU64 = AtomicU64::new(0);\nstatic KEY_ENV_OPEN_EVAL: AtomicU64 = AtomicU64::new(0);\nstatic KEY_ENV_LAMBDA: AtomicU64 = AtomicU64::new(0);\nstatic KEY_ENV_PI: AtomicU64 = AtomicU64::new(0);\n\npub fn report_key_env_producer_census() {\n    eprintln!(\"KEY_ENV_PRODUCER_CENSUS thunk={} open_eval={} lambda={} pi={}\",\n        KEY_ENV_THUNK.load(Ordering::Relaxed),\n        KEY_ENV_OPEN_EVAL.load(Ordering::Relaxed),\n        KEY_ENV_LAMBDA.load(Ordering::Relaxed),\n        KEY_ENV_PI.load(Ordering::Relaxed));\n}\n"""
assert needle in s
s = s.replace(needle, insert, 1)

needle = """    pub(crate) fn mk_thunk_hc(&mut self, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {\n        let te = self.key_env(env, e);\n"""
repl = """    pub(crate) fn mk_thunk_hc(&mut self, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {\n        KEY_ENV_THUNK.fetch_add(1, Ordering::Relaxed);\n        let te = self.key_env(env, e);\n"""
assert needle in s
s = s.replace(needle, repl, 1)

needle = """        if matches!(\n            self.ctx.read_expr_ref(e),\n            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }\n        ) {\n            let te = self.key_env(env, e);\n"""
repl = """        if matches!(\n            self.ctx.read_expr_ref(e),\n            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }\n        ) {\n            KEY_ENV_OPEN_EVAL.fetch_add(1, Ordering::Relaxed);\n            let te = self.key_env(env, e);\n"""
assert needle in s
s = s.replace(needle, repl, 1)

needle = """            Expr::Lambda { binder_name, binder_style, binder_type, body, .. } =>\n                {\n                let ce = self.key_env(env, e);\n"""
repl = """            Expr::Lambda { binder_name, binder_style, binder_type, body, .. } =>\n                {\n                KEY_ENV_LAMBDA.fetch_add(1, Ordering::Relaxed);\n                let ce = self.key_env(env, e);\n"""
assert needle in s
s = s.replace(needle, repl, 1)

needle = """                {\n                    let ce = self.key_env(env, e);\n                    value::mk_pi(self.arena, binder_name, binder_style, dom, Closure::mk_eval(ce, body))\n                }\n"""
repl = """                {\n                    KEY_ENV_PI.fetch_add(1, Ordering::Relaxed);\n                    let ce = self.key_env(env, e);\n                    value::mk_pi(self.arena, binder_name, binder_style, dom, Closure::mk_eval(ce, body))\n                }\n"""
assert needle in s
s = s.replace(needle, repl, 1)
p.write_text(s)

p = Path('src/main.rs')
s = p.read_text()
needle = """    export_file.check_all_declars();\n    // Pretty print as necessary\n"""
repl = """    export_file.check_all_declars();\n    sokonanoda::eval::report_key_env_producer_census();\n    // Pretty print as necessary\n"""
assert needle in s
s = s.replace(needle, repl, 1)
p.write_text(s)
print('applied key_env producer census v6')
