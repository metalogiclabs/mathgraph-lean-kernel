#!/usr/bin/env python3
"""Bypass redundant closed-expression memo for substitution-free Const atoms.

Soko eval() checks the generic closed EvalPtr cache, then eval_no_cache()
eventually calls eval_const(name, levels), itself canonicalized in the
const_head_value_cache.  With NO level substitution, eval_const returns
EXACTLY the same value; the outer expr cache is redundant. Keep the
original path whenever a universe-level substitution exists. Value
typing, proof rules, and rejects are entirely unchanged.
"""
from pathlib import Path
import sys
p=Path(sys.argv[1])/"src/checker/eval.rs"
s=p.read_text()
old="""    pub(crate) fn eval(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        if e.num_loose_bvars() == 0 {"""
new="""    pub(crate) fn eval(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        // A Const's result, with no universe substitution, is already
        // interned by eval_const's (name, levels) memo. Bypass the second,
        // redundant expression-pointer closed-eval memo; preserve the
        // original path for any nonempty universe substitution environment.
        if let &Expr::Const { name, levels, .. } = e.as_ref()
            && env.lsub().is_none()
        {
            return self.eval_const(name, levels);
        }
        if e.num_loose_bvars() == 0 {"""
assert s.count(old)==1, "Evaluator source identity changed"
assert s.count("pub(crate) fn eval_const(")==1, "Expected eval_const implementation absent"
assert s.count("Expr::Const { name, levels, .. } => {")==1, "Expected reference Const evaluation branch absent"
s=s.replace(old,new)
assert s.count(new)==1
p.write_text(s)
print("CONST_NO_LSUB_DOUBLE_MEMO_BYPASS=APPLIED",flush=True)
