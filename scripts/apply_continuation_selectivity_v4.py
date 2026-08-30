#!/usr/bin/env python3
from pathlib import Path
import argparse

ap = argparse.ArgumentParser()
ap.add_argument("path", nargs="?", default="src/eval.rs")
ap.add_argument("--mode", choices=("app", "app_lambda", "a6"), required=True)
a = ap.parse_args()

p = Path(a.path)
s = p.read_text()

# Historical E0024: App is a transient composition boundary. Do not pay the
# open-eval key_env/cache/canonicalization cost merely to immediately consume it.
old_cache = '''        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {
'''
if a.mode == "app":
    new_cache = '''        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {
'''
else:
    # Historical E0025: extend the same continuation-selectivity law to Lambda.
    new_cache = '''        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. }
        ) {
'''

n = s.count(old_cache)
if n != 1:
    raise SystemExit(f"open-eval cache site: expected 1, found {n}")
s = s.replace(old_cache, new_cache, 1)
print("APPLIED=E0024_app_open_eval_bypass")
if a.mode != "app":
    print("APPLIED=E0025_lambda_open_eval_bypass")

if a.mode == "a6":
    # Historical E0030: once Lambda is no longer a persistence/cache boundary,
    # carrying the raw environment is semantically sufficient. Let downstream
    # persistence boundaries call key_env when/if canonical identity is needed.
    old_lam = '''            Expr::Lambda { binder_name, binder_style, binder_type, body, .. } =>
                {
                let ce = self.key_env(env, e);
                value::mk_lam(self.arena, binder_name, binder_style, binder_type, Closure::mk_eval(ce, body))
            }
'''
    new_lam = '''            Expr::Lambda { binder_name, binder_style, binder_type, body, .. } =>
                value::mk_lam(self.arena, binder_name, binder_style, binder_type, Closure::mk_eval(env, body)),
'''
    n = s.count(old_lam)
    if n != 1:
        raise SystemExit(f"Lambda capture site: expected 1, found {n}")
    s = s.replace(old_lam, new_lam, 1)
    print("APPLIED=E0030_lambda_raw_env_capture")

p.write_text(s)
print(f"CONTINUATION_SELECTIVITY_MODE={a.mode}")
