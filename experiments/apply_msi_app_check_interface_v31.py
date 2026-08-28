from pathlib import Path
import sys

mode = sys.argv[1]
assert mode in {'preptr', 'generic_sort', 'app_sort'}

conv = Path('src/conv.rs')
s = conv.read_text()
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
preptr = r'''    #[inline]
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
generic_sort = r'''    #[inline]
    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
        if std::ptr::eq(x, y) {
            return true;
        }
        if let (Value::Sort { level: lx, .. }, Value::Sort { level: ly, .. }) = (x, y) {
            if lx == ly {
                return true;
            }
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
s = s.replace(old, generic_sort if mode == 'generic_sort' else preptr)
conv.write_text(s)

if mode == 'app_sort':
    infer = Path('src/infer.rs')
    s = infer.read_text()
    old_app = r'''            if flag == Check {
                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);
                assert!(self.conv_types_at(depth, domain, arg_ty), "app arg def_eq failed");
            }
'''
    new_app = r'''            if flag == Check {
                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);
                let app_ty_ok = match (domain, arg_ty) {
                    (
                        Value::Sort { level: domain_level, .. },
                        Value::Sort { level: arg_level, .. },
                    ) if domain_level == arg_level => true,
                    _ => self.conv_types_at(depth, domain, arg_ty),
                };
                assert!(app_ty_ok, "app arg def_eq failed");
            }
'''
    assert old_app in s, 'infer_app_v anchor not found'
    infer.write_text(s.replace(old_app, new_app))

print('applied MSI app-check interface v31', mode)
