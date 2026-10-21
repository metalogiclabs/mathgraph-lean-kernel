#!/usr/bin/env python3
"""Demand-driven beta reduction for unused lambda arguments.

The source checker already has a verified syntactic fv_mask rule
ignores_binder(body) = body.fv_mask & 1 == 0. In eval_spine() we may avoid
evaluating the argument when the bound variable does not occur anywhere in
the body, including nested binder types.

The checked application inference is unchanged and must continue checking
the argument against its dependent Pi binder type. The unused value position
is populated with the pre-existing placeholder() only to preserve the
original Env::Cons/binder depth semantics. This is source-scoped research,
NOT yet a proof of full Lean kernel soundness.
"""
from pathlib import Path
import sys
if len(sys.argv)!=2:raise SystemExit("usage: patch.py SOURCE_ROOT")
p=Path(sys.argv[1])/"src/checker/eval.rs"
s=p.read_text()
old="""                    let a = self.eval_arg(depth, env, rev_args[i]);
                    benv = self.env_extend(benv, a);"""
new="""                    // The beta argument is semantically unobservable when
                    // the kernel's source-owned support calculation proves
                    // that the bound variable is absent from this body.
                    // Validation of the argument belongs to infer_app_v,
                    // and is not weakened by this evaluation-only shortcut.
                    let a = if crate::term::expr::ignores_binder(body) {
                        self.placeholder()
                    } else {
                        self.eval_arg(depth, env, rev_args[i])
                    };
                    benv = self.env_extend(benv, a);"""
assert s.count(old)==1,("eval_spine exact source mismatch",s.count(old))
s=s.replace(old,new)
p.write_text(s)
print("FLASH_BETA_DEMAND=SKIP_EVAL_ONLY_WHEN_BINDER_SOURCE_MASK_PROVES_UNUSED",flush=True)
