from pathlib import Path

p=Path('src/infer.rs')
s=p.read_text()

s=s.replace('use InferFlag::*;\n', '''use InferFlag::*;\n\nuse std::sync::atomic::{AtomicBool, AtomicU64, Ordering};\n\nstatic MSI_V36_TOTAL: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V36_REPORTED: AtomicBool = AtomicBool::new(false);\nstatic MSI_V36_SORT_ENSURE: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V36_SORT_ENSURE_PRE: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V36_APP_PI: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V36_APP_PI_PRE: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V36_APP_SORT_PAIR: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V36_LET_SORT_PAIR: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V36_PROJ_IND: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V36_PROJ_IND_PRE: AtomicU64 = AtomicU64::new(0);\n\nfn msi_v36_tick() {\n    let n = MSI_V36_TOTAL.fetch_add(1, Ordering::Relaxed) + 1;\n    if n >= 1_000_000 && !MSI_V36_REPORTED.swap(true, Ordering::Relaxed) {\n        eprintln!(\n            "MSI_V36 total={} sort_ensure={} sort_ensure_pre={} app_pi={} app_pi_pre={} app_sort_pair={} let_sort_pair={} proj_ind={} proj_ind_pre={}",\n            n,\n            MSI_V36_SORT_ENSURE.load(Ordering::Relaxed),\n            MSI_V36_SORT_ENSURE_PRE.load(Ordering::Relaxed),\n            MSI_V36_APP_PI.load(Ordering::Relaxed),\n            MSI_V36_APP_PI_PRE.load(Ordering::Relaxed),\n            MSI_V36_APP_SORT_PAIR.load(Ordering::Relaxed),\n            MSI_V36_LET_SORT_PAIR.load(Ordering::Relaxed),\n            MSI_V36_PROJ_IND.load(Ordering::Relaxed),\n            MSI_V36_PROJ_IND_PRE.load(Ordering::Relaxed),\n        );\n    }\n}\n''')

old='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => *level,\n            _ => panic!("expected a sort"),\n        }\n    }'''
new='''    pub(crate) fn ensure_sort_v(&mut self, depth: u32, v: V<'t>) -> LevelPtr<'t> {\n        let pre = matches!(v, Value::Sort { .. });\n        match self.force_all(depth, v) {\n            Value::Sort { level , .. } => {\n                MSI_V36_SORT_ENSURE.fetch_add(1, Ordering::Relaxed);\n                if pre { MSI_V36_SORT_ENSURE_PRE.fetch_add(1, Ordering::Relaxed); }\n                msi_v36_tick();\n                *level\n            },\n            _ => panic!("expected a sort"),\n        }\n    }'''
assert old in s
s=s.replace(old,new)

old='''            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };'''
new='''            let pre_pi = matches!(fty, Value::Pi { .. });\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => {\n                    MSI_V36_APP_PI.fetch_add(1, Ordering::Relaxed);\n                    if pre_pi { MSI_V36_APP_PI_PRE.fetch_add(1, Ordering::Relaxed); }\n                    msi_v36_tick();\n                    (*domain, body)\n                },\n                _ => panic!("expected a pi type"),\n            };'''
assert old in s
s=s.replace(old,new,1)

old='''                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);\n                assert!(self.conv_types_at(depth, domain, arg_ty), "app arg def_eq failed");'''
new='''                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);\n                if matches!((domain, arg_ty), (Value::Sort { .. }, Value::Sort { .. })) {\n                    MSI_V36_APP_SORT_PAIR.fetch_add(1, Ordering::Relaxed);\n                    msi_v36_tick();\n                }\n                assert!(self.conv_types_at(depth, domain, arg_ty), "app arg def_eq failed");'''
assert old in s
s=s.replace(old,new,1)

old='''                    let val_ty = self.infer_value(flag, depth, env, ctx, val);\n                    assert!(self.conv_types_at(depth, dom, val_ty), "let def_eq failed");'''
new='''                    let val_ty = self.infer_value(flag, depth, env, ctx, val);\n                    if matches!((dom, val_ty), (Value::Sort { .. }, Value::Sort { .. })) {\n                        MSI_V36_LET_SORT_PAIR.fetch_add(1, Ordering::Relaxed);\n                        msi_v36_tick();\n                    }\n                    assert!(self.conv_types_at(depth, dom, val_ty), "let def_eq failed");'''
assert old in s
s=s.replace(old,new,1)

old='''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = self.force_all(depth, struct_ty);\n        let struct_ty_is_prop = self.is_prop_type(depth, struct_ty_f);\n        let (ind_name, ind_levels, spine) = match struct_ty_f {\n            Value::Rigid { head: RigidHead::Inductive(n, ls), spine, .. } => (*n, *ls, *spine),'''
new='''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let pre_ind = matches!(struct_ty, Value::Rigid { head: RigidHead::Inductive(..), .. });\n        let struct_ty_f = self.force_all(depth, struct_ty);\n        let struct_ty_is_prop = self.is_prop_type(depth, struct_ty_f);\n        let (ind_name, ind_levels, spine) = match struct_ty_f {\n            Value::Rigid { head: RigidHead::Inductive(n, ls), spine, .. } => {\n                MSI_V36_PROJ_IND.fetch_add(1, Ordering::Relaxed);\n                if pre_ind { MSI_V36_PROJ_IND_PRE.fetch_add(1, Ordering::Relaxed); }\n                msi_v36_tick();\n                (*n, *ls, *spine)\n            },'''
assert old in s
s=s.replace(old,new,1)

p.write_text(s)
print('applied MSI semantic rediscovery frontier v36')
