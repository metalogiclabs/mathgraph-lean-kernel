#!/usr/bin/env python3
"""Avoid re-pruning an already-keyed environment for an open Pi/Lambda.

In the pinned Soko eval(), every open Pi/Lambda is passed to eval_no_cache()
through the open_eval_cache branch, with env already computed as key_env(env,e).
An identical second key_env(env,e) in the Pi/Lambda arm is redundant:
prune_env returns the already-pruned Framed/Nil environment unchanged.
For closed Pi/Lambda, original key_env remains necessary to remove unrelated
bindings and preserve the exact level-substitution basis. No typing or proof
rule changes. Assertion pins the four caller sites of private eval_no_cache.
"""
from pathlib import Path
import sys
p=Path(sys.argv[1])/"src/checker/eval.rs"
s=p.read_text()
assert s.count("self.eval_no_cache(")==4, "Other direct callsites need a new proof"
old_lam="""            Expr::Lambda {
                binder_type, body, ..
            } => {
                let ce = self.key_env(env, e);
                self.mk_lam_hc(binder_type, Closure::mk_eval(ce, body))
            }"""
new_lam="""            Expr::Lambda {
                binder_type, body, ..
            } => {
                // eval() already keyed open Lambda's environment before cache
                // dispatch. Closed terms still need lsub_base canonicalization.
                let ce = if e.num_loose_bvars() == 0 {
                    self.key_env(env, e)
                } else {
                    env
                };
                self.mk_lam_hc(binder_type, Closure::mk_eval(ce, body))
            }"""
old_pi="""            Expr::Pi {
                binder_type, body, ..
            } => {
                let dom = self.eval(depth, env, binder_type);
                {
                    let ce = self.key_env(env, e);
                    self.mk_pi_hc(dom, Closure::mk_eval(ce, body))
                }
            }"""
new_pi="""            Expr::Pi {
                binder_type, body, ..
            } => {
                let dom = self.eval(depth, env, binder_type);
                {
                    let ce = if e.num_loose_bvars() == 0 {
                        self.key_env(env, e)
                    } else {
                        env
                    };
                    self.mk_pi_hc(dom, Closure::mk_eval(ce, body))
                }
            }"""
assert s.count(old_lam)==1 and s.count(old_pi)==1
assert "let te = self.key_env(env, e);" in s and "self.eval_no_cache(depth, te, e)" in s
s=s.replace(old_lam,new_lam).replace(old_pi,new_pi)
p.write_text(s)
print("KEYED_OPEN_PI_LAMBDA=REUSE_WITH_CLOSED_ENV_PROTECTION",flush=True)
