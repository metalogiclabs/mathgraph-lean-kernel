#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit('usage: v5_key_env_reuse_patch.py <worktree> <reuse|ablate>')
root = Path(sys.argv[1])
mode = sys.argv[2]
assert mode in {'reuse', 'ablate'}

# Add a session-scoped memo from raw (environment identity, expression) to the
# already-computed future-relative projected environment.  The ablation arm
# pays the same insertion/storage cost but deliberately never reads the memo.
p = root / 'src' / 'util.rs'
s = p.read_text()
old = "    pub(crate) open_eval_cache: FxHashMap<(usize, ExprPtr<'t>), V<'a>>,\n    pub(crate) open_eval_seen: FxHashSet<ExprPtr<'t>>,"
new = "    pub(crate) open_eval_cache: FxHashMap<(usize, ExprPtr<'t>), V<'a>>,\n    pub(crate) key_env_memo: FxHashMap<(usize, ExprPtr<'t>), E<'a>>,\n    pub(crate) open_eval_seen: FxHashSet<ExprPtr<'t>>,"
assert old in s, 'TcCache field site changed'
s = s.replace(old, new, 1)

old = "            open_eval_cache: session_fx_hash_map(),\n            open_eval_seen: small_fx_hash_set(),"
new = "            open_eval_cache: session_fx_hash_map(),\n            key_env_memo: session_fx_hash_map(),\n            open_eval_seen: small_fx_hash_set(),"
assert old in s, 'TcCache init site changed'
s = s.replace(old, new, 1)

old = "        self.open_eval_cache.clear();\n        self.open_eval_seen.clear();"
new = "        self.open_eval_cache.clear();\n        self.key_env_memo.clear();\n        self.open_eval_seen.clear();"
assert old in s, 'TcCache clear site changed'
s = s.replace(old, new, 1)

old = "        shrink_map(&mut self.open_eval_cache);\n        shrink_set(&mut self.open_eval_seen);"
new = "        shrink_map(&mut self.open_eval_cache);\n        shrink_map(&mut self.key_env_memo);\n        shrink_set(&mut self.open_eval_seen);"
assert old in s, 'TcCache clear_session site changed'
s = s.replace(old, new, 1)
p.write_text(s)

p = root / 'src' / 'eval.rs'
s = p.read_text()
old = '''    #[inline]\n    pub(crate) fn key_env(&mut self, env: E<'t>, e: ExprPtr<'t>) -> E<'t> {\n        let k = e.num_loose_bvars();\n        if k == 0 {\n            return self.lsub_base(env.lsub());\n        }\n        if k > 64 {\n            return env;\n        }\n        self.prune_env(env, e.as_ref().fv_mask())\n    }'''
lookup = '''        if let Some(r) = self.tc_cache.key_env_memo.get(&raw_key).copied() {\n            return r;\n        }\n''' if mode == 'reuse' else ''
new = f'''    #[inline]\n    pub(crate) fn key_env(&mut self, env: E<'t>, e: ExprPtr<'t>) -> E<'t> {{\n        let raw_key = (env as *const value::Env<'t> as usize, e);\n{lookup}        let k = e.num_loose_bvars();\n        let r = if k == 0 {{\n            self.lsub_base(env.lsub())\n        }} else if k > 64 {{\n            env\n        }} else {{\n            self.prune_env(env, e.as_ref().fv_mask())\n        }};\n        self.tc_cache.key_env_memo.insert(raw_key, r);\n        r\n    }}'''
assert old in s, 'key_env site changed'
s = s.replace(old, new, 1)
p.write_text(s)
