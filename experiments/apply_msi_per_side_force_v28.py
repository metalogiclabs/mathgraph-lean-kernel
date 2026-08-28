from pathlib import Path
import sys

mode = sys.argv[1]
assert mode in {'both_gate','per_side'}
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
if mode == 'both_gate':
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
else:
    new = r'''    #[inline]
    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
        if std::ptr::eq(x, y) {
            return true;
        }
        let xt = matches!(x, Value::Thunk { .. });
        let yt = matches!(y, Value::Thunk { .. });
        if !xt && !yt {
            return self.unify_general::<RIGID>(depth, x, y);
        }
        let x = if xt { self.force_thunk(depth, x) } else { x };
        let y = if yt { self.force_thunk(depth, y) } else { y };
        if std::ptr::eq(x, y) {
            return true;
        }
        self.unify_general::<RIGID>(depth, x, y)
    }
'''
assert old in s, 'unify anchor not found'
p.write_text(s.replace(old, new))
print(f'applied MSI per-side force v28 mode={mode}')
