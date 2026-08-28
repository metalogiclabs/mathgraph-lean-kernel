from pathlib import Path
import sys

mode = sys.argv[1]
assert mode in {'local', 'shared', 'ablate'}

p = Path('src/infer.rs')
s = p.read_text()

# A continuation-facing capability: retain the inferred value plus the already-visible
# raw Sort distinction at the inference boundary.  This intentionally does not alter
# Value, evaluation, conversion semantics, or the trusted result; it changes only what
# information the inference boundary exposes to its immediate consumers.
anchor = """#[derive(Debug, Clone, Copy)]
pub(crate) struct CachedType<'a> {
    pub(crate) result: V<'a>,
    pub(crate) checked_under: CheckScope<'a>,
}
"""
insert = anchor + """
#[derive(Debug, Clone, Copy)]
pub(crate) struct InferCap<'a> {
    pub(crate) value: V<'a>,
    pub(crate) sort_level: Option<LevelPtr<'a>>,
}
"""
assert anchor in s
s = s.replace(anchor, insert)

# Add one boundary operation.  The local arm still uses ordinary infer_value below;
# shared/ablate construct this object once at the producer-consumer boundary.
impl_anchor = """impl<'x, 't, 'p> TypeChecker<'x, 't, 'p> {
    fn uparam_scope(&self) -> CheckScope<'t> {
"""
impl_repl = """impl<'x, 't, 'p> TypeChecker<'x, 't, 'p> {
    #[inline]
    fn infer_cap(
        &mut self,
        flag: InferFlag,
        depth: u32,
        env: E<'t>,
        ctx: C<'t>,
        e: ExprPtr<'t>,
    ) -> InferCap<'t> {
        let value = self.infer_value(flag, depth, env, ctx, e);
        let sort_level = match value {
            Value::Sort { level, .. } => Some(*level),
            _ => None,
        };
        InferCap { value, sort_level }
    }

    fn uparam_scope(&self) -> CheckScope<'t> {
"""
assert impl_anchor in s
s = s.replace(impl_anchor, impl_repl)

# Consumer 1: sort requirement.  In shared mode consume the capability directly;
# ablate deliberately ignores it and reconstructs through ensure_sort_v.
old_sort = """    pub(crate) fn infer_sort_of_v(
        &mut self,
        flag: InferFlag,
        depth: u32,
        env: E<'t>,
        ctx: C<'t>,
        e: ExprPtr<'t>,
    ) -> LevelPtr<'t> {
        let t = self.infer_value(flag, depth, env, ctx, e);
        self.ensure_sort_v(depth, t)
    }
"""
if mode == 'local':
    new_sort = old_sort
elif mode == 'shared':
    new_sort = """    pub(crate) fn infer_sort_of_v(
        &mut self,
        flag: InferFlag,
        depth: u32,
        env: E<'t>,
        ctx: C<'t>,
        e: ExprPtr<'t>,
    ) -> LevelPtr<'t> {
        let cap = self.infer_cap(flag, depth, env, ctx, e);
        match cap.sort_level {
            Some(level) => level,
            None => self.ensure_sort_v(depth, cap.value),
        }
    }
"""
else:
    new_sort = """    pub(crate) fn infer_sort_of_v(
        &mut self,
        flag: InferFlag,
        depth: u32,
        env: E<'t>,
        ctx: C<'t>,
        e: ExprPtr<'t>,
    ) -> LevelPtr<'t> {
        let cap = self.infer_cap(flag, depth, env, ctx, e);
        let _ablated = cap.sort_level;
        self.ensure_sort_v(depth, cap.value)
    }
"""
assert old_sort in s
s = s.replace(old_sort, new_sort)

old_app = """            if flag == Check {
                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);
                assert!(self.conv_types_at(depth, domain, arg_ty), \"app arg def_eq failed\");
            }
"""
if mode == 'local':
    new_app = """            if flag == Check {
                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);
                let ok = match (domain, arg_ty) {
                    (Value::Sort { level: dl, .. }, Value::Sort { level: al, .. }) if dl == al => true,
                    _ => self.conv_types_at(depth, domain, arg_ty),
                };
                assert!(ok, \"app arg def_eq failed\");
            }
"""
elif mode == 'shared':
    new_app = """            if flag == Check {
                let cap = self.infer_cap(flag, depth, env, ctx, arg);
                let ok = match (domain, cap.sort_level) {
                    (Value::Sort { level: dl, .. }, Some(al)) if *dl == al => true,
                    _ => self.conv_types_at(depth, domain, cap.value),
                };
                assert!(ok, \"app arg def_eq failed\");
            }
"""
else:
    new_app = """            if flag == Check {
                let cap = self.infer_cap(flag, depth, env, ctx, arg);
                let _ablated = cap.sort_level;
                assert!(self.conv_types_at(depth, domain, cap.value), \"app arg def_eq failed\");
            }
"""
assert old_app in s
s = s.replace(old_app, new_app)

# Consumer 3: let value-type compatibility.  Same exact Sort separator, either local,
# shared through InferCap, or ablated after construction.
old_let = """                    let val_ty = self.infer_value(flag, depth, env, ctx, val);
                    assert!(self.conv_types_at(depth, dom, val_ty), \"let def_eq failed\");
"""
if mode == 'local':
    new_let = """                    let val_ty = self.infer_value(flag, depth, env, ctx, val);
                    let ok = match (dom, val_ty) {
                        (Value::Sort { level: dl, .. }, Value::Sort { level: vl, .. }) if dl == vl => true,
                        _ => self.conv_types_at(depth, dom, val_ty),
                    };
                    assert!(ok, \"let def_eq failed\");
"""
elif mode == 'shared':
    new_let = """                    let cap = self.infer_cap(flag, depth, env, ctx, val);
                    let ok = match (dom, cap.sort_level) {
                        (Value::Sort { level: dl, .. }, Some(vl)) if *dl == vl => true,
                        _ => self.conv_types_at(depth, dom, cap.value),
                    };
                    assert!(ok, \"let def_eq failed\");
"""
else:
    new_let = """                    let cap = self.infer_cap(flag, depth, env, ctx, val);
                    let _ablated = cap.sort_level;
                    assert!(self.conv_types_at(depth, dom, cap.value), \"let def_eq failed\");
"""
assert old_let in s
s = s.replace(old_let, new_let)

p.write_text(s)
print('applied MSI Sort interface regenesis v37', mode)
