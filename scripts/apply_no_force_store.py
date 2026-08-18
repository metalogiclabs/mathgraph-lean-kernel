#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
p = root / 'src' / 'eval.rs'
s = p.read_text()
old = '''    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {\n            return r;\n        }\n        let mut cur = v;\n        let mut steps = 0u32;'''
new = '''    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        let mut cur = v;\n        let mut steps = 0u32;'''
assert old in s, 'force_all entry anchor not found'
s = s.replace(old, new, 1)
old2 = '''        self.note_whnf(depth, v, result, steps);\n        result\n    }\n\n    fn iota_step'''
new2 = '''        let _ = steps;\n        result\n    }\n\n    fn iota_step'''
assert old2 in s, 'force_all note_whnf anchor not found'
s = s.replace(old2, new2, 1)
p.write_text(s)
print('no-force-store ablation applied')
