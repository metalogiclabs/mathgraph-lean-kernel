from pathlib import Path

p = Path('src/conv.rs')
s = p.read_text()
old = r'''    #[inline]
    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
        let x = self.force_thunk(depth, x);
        let y = self.force_thunk(depth, y);
        if std::ptr::eq(x, y) {
            return true;
        }
        self.unify_general::<RIGID>(depth, x, y)
    }
'''
new = r'''    #[inline]
    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
        if std::ptr::eq(x, y) {
            return true;
        }
        if !matches!(x, Value::Thunk { .. }) && !matches!(y, Value::Thunk { .. }) {
            return self.unify_general::<RIGID>(depth, x, y);
        }
        let x = self.force_thunk(depth, x);
        let y = self.force_thunk(depth, y);
        if std::ptr::eq(x, y) {
            return true;
        }
        self.unify_general::<RIGID>(depth, x, y)
    }
'''
assert old in s, 'unify anchor not found'
p.write_text(s.replace(old, new))
print('applied MSI V24 non-thunk transfer candidate')
