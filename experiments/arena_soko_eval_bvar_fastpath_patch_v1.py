#!/usr/bin/env python3
"""Identity-preserving evaluator dispatch on the fully qualified Soko source.

Var nodes cannot be closed (they contain a loose de Bruijn index).
The original eval() falls through num_loose_bvars / shape tests and then
eval_no_cache() before executing exactly this environment lookup. Bypass
that redundant dispatch. No conversion/proof/typing rules change.
"""
from pathlib import Path
import sys
p=Path(sys.argv[1])/"src/checker/eval.rs"
s=p.read_text()
old="    pub(crate) fn eval(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {\n        if e.num_loose_bvars() == 0 {"
new="""    pub(crate) fn eval(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {
        // Same judgment as eval_no_cache's Expr::Var arm, before the
        // free-variable and cache-dispatch tests. Var is never closed.
        if let &Expr::Var { dbj_idx, .. } = e.as_ref() {
            return env.lookup(dbj_idx).expect("eval: loose bvar");
        }
        if e.num_loose_bvars() == 0 {"""
assert s.count(old)==1,"Pinned evaluator preamble changed"
assert s.count('Expr::Var { dbj_idx, .. } => env.lookup(dbj_idx).expect("eval: loose bvar")')==1, "Expected reference arm absent"
s=s.replace(old,new)
assert s.count(new)==1
p.write_text(s)
print("EVAL_BVAR_DIRECT_LOOKUP=APPLIED_EXACT_EXISTING_ARM",flush=True)
