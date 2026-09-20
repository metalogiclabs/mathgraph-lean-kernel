#!/usr/bin/env python3
from pathlib import Path

# --- infer.rs ---
p=Path("src/infer.rs")
c=p.read_text()

old="""    fn uparam_scope(&self) -> CheckScope<'t> {
        match self.declar_info {
            Some(info) => CheckScope::Under(info.uparams),
            None => CheckScope::NoUparams,
        }
    }
"""
new="""    fn expr_is_uparam_free(&mut self, root: ExprPtr<'t>) -> bool {
        if let Some(&r) = self.tc_cache.uparam_free_expr_cache.get(&root) {
            return r;
        }

        fn level_has_param<'x, 't, 'p>(
            tc: &mut TypeChecker<'x, 't, 'p>,
            root: LevelPtr<'t>,
        ) -> bool {
            let mut stack = vec![root];
            while let Some(l) = stack.pop() {
                match tc.ctx.read_level(l) {
                    crate::level::Level::Zero => {}
                    crate::level::Level::Param(..) => return true,
                    crate::level::Level::Succ(x, ..) => stack.push(x),
                    crate::level::Level::Max(a, b, ..) | crate::level::Level::IMax(a, b, ..) => {
                        stack.push(a);
                        stack.push(b);
                    }
                }
            }
            false
        }

        let mut stack = vec![root];
        let mut seen = crate::util::small_fx_hash_set();
        let mut free = true;
        while let Some(e) = stack.pop() {
            if !seen.insert(e) {
                continue;
            }
            match self.ctx.read_expr(e) {
                Var { .. } | NatLit { .. } | StringLit { .. } => {}
                Sort { level, .. } => {
                    if level_has_param(self, level) {
                        free = false;
                        break;
                    }
                }
                Const { levels, .. } => {
                    for l in self.ctx.read_levels(levels).iter().copied() {
                        if level_has_param(self, l) {
                            free = false;
                            break;
                        }
                    }
                    if !free {
                        break;
                    }
                }
                App { fun, arg, .. } => {
                    stack.push(fun);
                    stack.push(arg);
                }
                Pi { binder_type, body, .. } | Lambda { binder_type, body, .. } => {
                    stack.push(binder_type);
                    stack.push(body);
                }
                Let { data: &crate::expr::LetData { binder_type, val, body, .. }, .. } => {
                    stack.push(binder_type);
                    stack.push(val);
                    stack.push(body);
                }
                Proj { structure, .. } => stack.push(structure),
            }
        }
        self.tc_cache.uparam_free_expr_cache.insert(root, free);
        free
    }

    fn uparam_scope(&mut self, e: ExprPtr<'t>) -> CheckScope<'t> {
        match self.declar_info {
            Some(info) if self.ctx.read_levels(info.uparams).is_empty() || self.expr_is_uparam_free(e) =>
                CheckScope::NoUparams,
            Some(info) => CheckScope::Under(info.uparams),
            None => CheckScope::NoUparams,
        }
    }
"""
if c.count(old) != 1:
    raise SystemExit(f"uparam_scope anchor mismatch: {c.count(old)}")
c=c.replace(old,new,1)

old2="""        let scope = self.uparam_scope();
"""
new2="""        let scope = self.uparam_scope(e);
"""
if c.count(old2) != 1:
    raise SystemExit(f"scope call anchor mismatch: {c.count(old2)}")
c=c.replace(old2,new2,1)
p.write_text(c)

# --- util.rs ---
p=Path("src/util.rs")
c=p.read_text()

old="""    pub(crate) type_cache: FxHashMap<(usize, ExprPtr<'t>), crate::infer::CachedType<'a>>,
"""
new="""    pub(crate) type_cache: FxHashMap<(usize, ExprPtr<'t>), crate::infer::CachedType<'a>>,
    pub(crate) uparam_free_expr_cache: FxHashMap<ExprPtr<'t>, bool>,
"""
if c.count(old) != 1:
    raise SystemExit(f"type_cache field anchor mismatch: {c.count(old)}")
c=c.replace(old,new,1)

old="""            type_cache: session_fx_hash_map(),
"""
new="""            type_cache: session_fx_hash_map(),
            uparam_free_expr_cache: session_small_fx_hash_map(),
"""
if c.count(old) != 1:
    raise SystemExit(f"type_cache init anchor mismatch: {c.count(old)}")
c=c.replace(old,new,1)

old="""        shrink_map(&mut self.type_cache);
"""
new="""        shrink_map(&mut self.type_cache);
        shrink_map(&mut self.uparam_free_expr_cache);
"""
if c.count(old) != 1:
    raise SystemExit(f"type_cache clear anchor mismatch: {c.count(old)}")
c=c.replace(old,new,1)

p.write_text(c)
print("QCKN_CHECKED_CAPABILITY_V2_PATCH=PASS")
