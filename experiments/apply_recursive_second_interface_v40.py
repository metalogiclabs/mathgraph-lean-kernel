from pathlib import Path
import json, sys

if len(sys.argv) != 3:
    raise SystemExit('usage: apply_recursive_second_interface_v40.py SELECTION_JSON MODE')
sel=json.loads(Path(sys.argv[1]).read_text())
mode=sys.argv[2]
assert mode in {'local','shared','ablate'}
winner=sel['winner_materializer']
assert winner in {'pi','inductive'}

p=Path('src/infer.rs')
s=p.read_text()

# V40 always starts after the frozen V39 Sort shared interface has been materialized.
old_struct="""#[derive(Debug, Clone, Copy)]
pub(crate) struct InferCap<'a> {
    pub(crate) value: V<'a>,
    pub(crate) sort_level: Option<LevelPtr<'a>>,
}
"""
new_struct="""#[derive(Debug, Clone, Copy)]
pub(crate) struct InferCap<'a> {
    pub(crate) value: V<'a>,
    pub(crate) sort_level: Option<LevelPtr<'a>>,
    pub(crate) pi_direct: bool,
    pub(crate) inductive_direct: bool,
}
"""
assert old_struct in s
s=s.replace(old_struct,new_struct,1)

old_ret="""        let sort_level = match value {
            Value::Sort { level, .. } => Some(*level),
            _ => None,
        };
        InferCap { value, sort_level }
"""
new_ret="""        let sort_level = match value {
            Value::Sort { level, .. } => Some(*level),
            _ => None,
        };
        let pi_direct = matches!(value, Value::Pi { .. });
        let inductive_direct = matches!(value, Value::Rigid { head: RigidHead::Inductive(..), .. });
        InferCap { value, sort_level, pi_direct, inductive_direct }
"""
assert old_ret in s
s=s.replace(old_ret,new_ret,1)

if winner == 'pi':
    old="""        let (fun, mut args) = self.ctx.unfold_apps_stack(self.arena, e);
        let mut fty = self.infer_value(flag, depth, env, ctx, fun);
        while let Some(arg) = args.pop() {
            let fty_f = self.force_all(depth, fty);
            let (domain, body) = match fty_f {
                Value::Pi { domain, body, .. } => (*domain, body),
                _ => panic!(\"expected a pi type\"),
            };
"""
    if mode=='local':
        new="""        let (fun, mut args) = self.ctx.unfold_apps_stack(self.arena, e);
        let mut fty = self.infer_value(flag, depth, env, ctx, fun);
        while let Some(arg) = args.pop() {
            let fty_f = match fty { Value::Pi { .. } => fty, _ => self.force_all(depth, fty) };
            let (domain, body) = match fty_f {
                Value::Pi { domain, body, .. } => (*domain, body),
                _ => panic!(\"expected a pi type\"),
            };
"""
    elif mode=='shared':
        new="""        let (fun, mut args) = self.ctx.unfold_apps_stack(self.arena, e);
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
        new="""        let (fun, mut args) = self.ctx.unfold_apps_stack(self.arena, e);
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
    s=s.replace(old,new,1)
else:
    old="""        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);
        let struct_ty_f = self.force_all(depth, struct_ty);
        let struct_ty_is_prop = self.is_prop_type(depth, struct_ty_f);
"""
    if mode=='local':
        new="""        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);
        let struct_ty_f = match struct_ty {
            Value::Rigid { head: RigidHead::Inductive(..), .. } => struct_ty,
            _ => self.force_all(depth, struct_ty),
        };
        let struct_ty_is_prop = self.is_prop_type(depth, struct_ty_f);
"""
    elif mode=='shared':
        new="""        let cap = self.infer_cap(flag, depth, env, ctx, structure);
        let struct_ty = cap.value;
        let struct_ty_f = if cap.inductive_direct { struct_ty } else { self.force_all(depth, struct_ty) };
        let struct_ty_is_prop = self.is_prop_type(depth, struct_ty_f);
"""
    else:
        new="""        let cap = self.infer_cap(flag, depth, env, ctx, structure);
        let _ablated = cap.inductive_direct;
        let struct_ty = cap.value;
        let struct_ty_f = self.force_all(depth, struct_ty);
        let struct_ty_is_prop = self.is_prop_type(depth, struct_ty_f);
"""
    assert old in s
    s=s.replace(old,new,1)

p.write_text(s)
print('applied V40 second interface', winner, mode)
