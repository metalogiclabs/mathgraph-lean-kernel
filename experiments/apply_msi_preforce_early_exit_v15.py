from pathlib import Path
p = Path('src/conv.rs')
s = p.read_text()
old = '''    #[inline]\n    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {\n        let x = self.force_thunk(depth, x);\n        let y = self.force_thunk(depth, y);\n        if std::ptr::eq(x, y) {\n            return true;\n        }\n        self.unify_general::<RIGID>(depth, x, y)\n    }\n'''
new = '''    #[inline]\n    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {\n        if std::ptr::eq(x, y) {\n            return true;\n        }\n        let x = self.force_thunk(depth, x);\n        let y = self.force_thunk(depth, y);\n        if std::ptr::eq(x, y) {\n            return true;\n        }\n        self.unify_general::<RIGID>(depth, x, y)\n    }\n'''
if old not in s:
    raise SystemExit('unify pattern not found')
p.write_text(s.replace(old, new, 1))
print('applied MSI pre-force early exit v15')
