from pathlib import Path

p = Path('src/conv.rs')
s = p.read_text()
old = '''    #[inline]\n    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {\n        let x = self.force_thunk(depth, x);\n        let y = self.force_thunk(depth, y);\n        if std::ptr::eq(x, y) {\n            return true;\n        }\n        self.unify_general::<RIGID>(depth, x, y)\n    }\n'''
new = '''    #[inline]\n    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {\n        // MSI v21: consume already-proven semantic identity before any stronger reconstruction.\n        if std::ptr::eq(x, y) {\n            return true;\n        }\n        // Only query the learned conversion relation when both raw values are already\n        // cacheable non-thunks. In that case force_thunk would be a no-op, and any UF\n        // hit is an exact equality class established by an earlier successful conversion.\n        if is_cacheable(x) && is_cacheable(y) {\n            let xa = x as *const Value<'t> as usize;\n            let ya = y as *const Value<'t> as usize;\n            if self.tc_cache.conv_uf.equiv(xa, ya) {\n                return true;\n            }\n        }\n        let x = self.force_thunk(depth, x);\n        let y = self.force_thunk(depth, y);\n        if std::ptr::eq(x, y) {\n            return true;\n        }\n        self.unify_general::<RIGID>(depth, x, y)\n    }\n'''
if old not in s:
    raise SystemExit('target unify block not found')
p.write_text(s.replace(old, new, 1))
print('applied MSI proven convref v21')
