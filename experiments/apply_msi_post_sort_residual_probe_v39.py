from pathlib import Path

p = Path('src/infer.rs')
s = p.read_text()

anchor = 'use InferFlag::*;\n'
assert anchor in s
s = s.replace(anchor, anchor + '''\nuse std::sync::atomic::{AtomicU64, Ordering};\n\nstatic MSI_V39_APP_PI: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V39_APP_PI_PRE: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V39_PROJ_IND: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V39_PROJ_IND_PRE: AtomicU64 = AtomicU64::new(0);\n\nfn msi_v39_report() {\n    eprintln!(\n        "MSI_V39_POST_SORT app_pi={} app_pi_pre={} proj_ind={} proj_ind_pre={}",\n        MSI_V39_APP_PI.load(Ordering::Relaxed),\n        MSI_V39_APP_PI_PRE.load(Ordering::Relaxed),\n        MSI_V39_PROJ_IND.load(Ordering::Relaxed),\n        MSI_V39_PROJ_IND_PRE.load(Ordering::Relaxed),\n    );\n}\n''', 1)

old_pi = '''            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => (*domain, body),\n                _ => panic!("expected a pi type"),\n            };'''
new_pi = '''            let pre_pi = matches!(fty, Value::Pi { .. });\n            let fty_f = self.force_all(depth, fty);\n            let (domain, body) = match fty_f {\n                Value::Pi { domain, body, .. } => {\n                    MSI_V39_APP_PI.fetch_add(1, Ordering::Relaxed);\n                    if pre_pi { MSI_V39_APP_PI_PRE.fetch_add(1, Ordering::Relaxed); }\n                    (*domain, body)\n                },\n                _ => panic!("expected a pi type"),\n            };'''
assert old_pi in s
s = s.replace(old_pi, new_pi, 1)

old_proj = '''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let struct_ty_f = self.force_all(depth, struct_ty);\n        let struct_ty_is_prop = self.is_prop_type(depth, struct_ty_f);\n        let (ind_name, ind_levels, spine) = match struct_ty_f {\n            Value::Rigid { head: RigidHead::Inductive(n, ls), spine, .. } => (*n, *ls, *spine),'''
new_proj = '''        let struct_ty = self.infer_value(flag, depth, env, ctx, structure);\n        let pre_ind = matches!(struct_ty, Value::Rigid { head: RigidHead::Inductive(..), .. });\n        let struct_ty_f = self.force_all(depth, struct_ty);\n        let struct_ty_is_prop = self.is_prop_type(depth, struct_ty_f);\n        let (ind_name, ind_levels, spine) = match struct_ty_f {\n            Value::Rigid { head: RigidHead::Inductive(n, ls), spine, .. } => {\n                MSI_V39_PROJ_IND.fetch_add(1, Ordering::Relaxed);\n                if pre_ind { MSI_V39_PROJ_IND_PRE.fetch_add(1, Ordering::Relaxed); }\n                msi_v39_report();\n                (*n, *ls, *spine)\n            },'''
assert old_proj in s
s = s.replace(old_proj, new_proj, 1)

p.write_text(s)
print('applied MSI post-Sort residual probe v39')
