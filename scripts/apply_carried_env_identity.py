#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
p = root / 'src' / 'infer.rs'
s = p.read_text()

old_key = '''        let key = (self.key_env(env, e) as *const value::Env<'t> as usize, e);\n        let scope = self.uparam_scope();'''
new_key = '''        // Canonical environment identity is part of the state of this inference.\n        // Do not compute it only for the cache key and then discard it: carrying\n        // the canonical frame forward prevents descendants from repeatedly\n        // rediscovering the same long Cons-chain projection.\n        let env = self.key_env(env, e);\n        let key = (env as *const value::Env<'t> as usize, e);\n        let scope = self.uparam_scope();'''
assert old_key in s, 'infer cache-key site changed'
s = s.replace(old_key, new_key, 1)

old_clo = 'let clo = Closure::mk_infer(self.key_env(env, e), ctx, body);'
new_clo = 'let clo = Closure::mk_infer(env, ctx, body);'
assert old_clo in s, 'lambda closure canonicalization site changed'
s = s.replace(old_clo, new_clo, 1)

p.write_text(s)
