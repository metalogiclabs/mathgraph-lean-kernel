from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_blind_kernel_interface_v38.py SELECTION_JSON MODE")
selection = json.loads(Path(sys.argv[1]).read_text())
mode = sys.argv[2]
if mode not in {"local", "shared", "ablate"}:
    raise SystemExit(f"bad mode {mode}")
winner = selection["winner_materializer"]

# Reuse the already-frozen causal materializer for the c0 capability. The selector
# chooses whether this materializer is used; the workflow never names it in advance.
if winner == "sort":
    script = Path(__file__).with_name("apply_msi_sort_interface_regenesis_v37.py")
    cp = subprocess.run([sys.executable, str(script), mode], text=True)
    raise SystemExit(cp.returncode)

p = Path("src/infer.rs")
s = p.read_text()

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
    pub(crate) pi_direct: bool,
    pub(crate) inductive_direct: bool,
}
"""
assert anchor in s
s = s.replace(anchor, insert)

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
        let pi_direct = matches!(value, Value::Pi { .. });
        let inductive_direct = matches!(value, Value::Rigid { head: RigidHead::Inductive(..), .. });
        InferCap { value, pi_direct, inductive_direct }
    }

    fn uparam_scope(&self) -> CheckScope<'t> {
"""
assert impl_anchor in s
s = s.replace(impl_anchor, impl_repl)

if winner == "pi":
    old = """        let (fun, mut args) = self.ctx.unfold_apps_stack(self.arena, e);
        let mut fty = self.infer_value(flag, depth, env, ctx, fun);
        while let Some(arg) = args.pop() {
            let fty_f = self.force_all(depth, fty);
            let (domain, body) = match fty_f {
                Value::Pi { domain, body, .. } => (*domain, body),
                _ => panic!(\"expected a pi type\"),
            };
"""
    if mode == "local":
        new = """        let (fun, mut args) = self.ctx.unfold_apps_stack(self.arena, e);
        let mut fty = self.infer_value(flag, depth, env, ctx, fun);
        while let Some(arg) = args.pop() {
            let fty_f = match fty {
                Value::Pi { .. } => fty,
                _ => self.force_all(depth, fty),
            };
            let (domain, body) = match fty_f {
                Value::Pi { domain, body, .. } => (*domain, body),
                _ => panic!(\"expected a pi type\"),
            };
"""
    elif mode == "shared":
        new = """        let (fun, mut args) = self.ctx.unfold_apps_stack(self.arena, e);
        let cap = self.infer_cap(flag, depth, env, ctx, fun);
        let mut fty = cap.value;
        let mut direct_pi = cap.pi_direct;
        while let Some(arg) = args.pop() {
            let fty_f = if direct_pi { fty } else { self.force_all(depth, fty) };
            let (domain, body) = match fty_f {
                Value::Pi { domain, body, .. } => (*domain, body),
                _ => panic!(\"expected a pi type\"),
            };
            direct_pi = false;
"""
    else:
        new = """        let (fun, mut args) = self.ctx.unfold_apps_stack(self.arena, e);
        let cap = self.infer_cap(flag, depth, env, ctx, fun);
        let _ablated = cap.pi_direct;
        let mut fty = cap.value;
        while let Some(arg) = args.pop() {
            let fty_f = self.force_all(depth, fty);
            let (domain, body) = match fty_f {
                Value::Pi { domain, body, .. } => (*domain, body),
                _ => panic!(\"expected a pi type\"),
            };
"""
    assert old in s
    s = s.replace(old, new, 1)
elif winner == "inductive":
    old = """        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);
        let struct_ty_f = self.force_all(depth, struct_ty);
        let struct_ty_is_prop = self.is_prop_type(depth, struct_ty_f);
"""
    if mode == "local":
        new = """        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);
        let struct_ty_f = match struct_ty {
            Value::Rigid { head: RigidHead::Inductive(..), .. } => struct_ty,
            _ => self.force_all(depth, struct_ty),
        };
        let struct_ty_is_prop = self.is_prop_type(depth, struct_ty_f);
"""
    elif mode == "shared":
        new = """        let cap = self.infer_cap(flag, depth, env, ctx, structure);
        let struct_ty = cap.value;
        let struct_ty_f = if cap.inductive_direct { struct_ty } else { self.force_all(depth, struct_ty) };
        let struct_ty_is_prop = self.is_prop_type(depth, struct_ty_f);
"""
    else:
        new = """        let cap = self.infer_cap(flag, depth, env, ctx, structure);
        let _ablated = cap.inductive_direct;
        let struct_ty = cap.value;
        let struct_ty_f = self.force_all(depth, struct_ty);
        let struct_ty_is_prop = self.is_prop_type(depth, struct_ty_f);
"""
    assert old in s
    s = s.replace(old, new, 1)
else:
    raise SystemExit(f"unsupported selected materializer {winner}")

p.write_text(s)
print("applied MSI blind kernel interface v38", winner, mode)
