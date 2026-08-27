#!/usr/bin/env python3
from pathlib import Path
p = Path('src/eval.rs')
s = p.read_text()
old = '''    #[inline]\n    pub(crate) fn key_env(&mut self, env: E<'t>, e: ExprPtr<'t>) -> E<'t> {\n        let k = e.num_loose_bvars();\n        if k == 0 {\n            return self.lsub_base(env.lsub());\n        }\n        if k > 64 {\n            return env;\n        }\n        self.prune_env(env, e.as_ref().fv_mask())\n    }\n'''
new = '''    #[inline]\n    pub(crate) fn key_env(&mut self, env: E<'t>, e: ExprPtr<'t>) -> E<'t> {\n        let k = e.num_loose_bvars();\n        if k == 0 {\n            return self.lsub_base(env.lsub());\n        }\n        // Experimental ablation: retain the full environment for open terms.\n        // This is semantically conservative; it removes environment pruning and\n        // exposes the net cost/benefit of prune_env_cold plus the sharing it buys.\n        env\n    }\n'''
if old not in s:
    raise SystemExit('key_env anchor not found')
p.write_text(s.replace(old, new, 1))
print('applied prune-env ablation')
