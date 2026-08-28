from pathlib import Path
import sys

mode=sys.argv[1]
assert mode in {'rigid','closure','unfold','direct'}
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
conds={
'rigid': r'''matches!((x, y), (Value::Rigid { .. }, Value::Rigid { .. }))''',
'closure': r'''matches!((x, y),
            (Value::Pi { .. }, Value::Pi { .. }) |
            (Value::Lam { .. }, Value::Lam { .. }))''',
'unfold': r'''matches!((x, y), (Value::Unfold { .. }, Value::Unfold { .. }))''',
'direct': r'''matches!((x, y),
            (Value::Sort { .. }, Value::Sort { .. }) |
            (Value::NatLit { .. }, Value::NatLit { .. }) |
            (Value::StrLit { .. }, Value::StrLit { .. }) |
            (Value::Rigid { .. }, Value::Rigid { .. }) |
            (Value::Pi { .. }, Value::Pi { .. }) |
            (Value::Lam { .. }, Value::Lam { .. }) |
            (Value::Unfold { .. }, Value::Unfold { .. }))''',
}
cond=conds[mode]
new=f'''    #[inline]\n    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {{\n        if std::ptr::eq(x, y) {{\n            return true;\n        }}\n        // MSI v26: consume a proven non-thunk fact only for the selected\n        // conversion family, rather than globally as in v24/v25.\n        if {cond} {{\n            return self.unify_general::<RIGID>(depth, x, y);\n        }}\n        let x = self.force_thunk(depth, x);\n        let y = self.force_thunk(depth, y);\n        if std::ptr::eq(x, y) {{\n            return true;\n        }}\n        self.unify_general::<RIGID>(depth, x, y)\n    }}\n'''
assert old in s, 'unify anchor not found'
p.write_text(s.replace(old,new))
print('applied',mode)
