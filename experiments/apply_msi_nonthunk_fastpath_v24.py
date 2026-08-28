from pathlib import Path
import sys

mode=sys.argv[1]
assert mode in {'preptr','nonthunk'}
p=Path('src/conv.rs')
s=p.read_text()
old=r'''    #[inline]
    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
        let x = self.force_thunk(depth, x);
        let y = self.force_thunk(depth, y);
        if std::ptr::eq(x, y) {
            return true;
        }
        self.unify_general::<RIGID>(depth, x, y)
    }
'''
if mode=='preptr':
    new=r'''    #[inline]
    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
        if std::ptr::eq(x, y) {
            return true;
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
    new=r'''    #[inline]
    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
        if std::ptr::eq(x, y) {
            return true;
        }
        // MSI v24: if neither side is a thunk, forcing cannot change either
        // value. Consume conversion/cache structure directly instead of
        // rediscovering the no-thunk fact through two force_thunk calls.
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
p.write_text(s.replace(old,new))
print('applied',mode)
