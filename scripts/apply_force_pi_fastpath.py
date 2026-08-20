#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / 'src' / 'eval.rs'
s = p.read_text()
old = '''    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {\n            return r;\n        }'''
new = '''    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        // A Pi is already WHNF by construction. This is a semantic fast path, not a cache heuristic.\n        if matches!(v, Value::Pi { .. }) {\n            return v;\n        }\n        if let Some(r) = self.store_lookup(depth, v) {\n            return r;\n        }'''
assert old in s
p.write_text(s.replace(old, new, 1))
print('applied exact Pi-WHNF force_all fast path')
