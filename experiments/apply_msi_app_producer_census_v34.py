from pathlib import Path

p = Path('src/infer.rs')
s = p.read_text()

s = s.replace(
    'use InferFlag::*;\n',
    'use InferFlag::*;\nuse std::sync::atomic::{AtomicBool, AtomicU64, Ordering};\n\nstatic MSI_APP_EQ_SORT_TOTAL: AtomicU64 = AtomicU64::new(0);\nstatic MSI_APP_EQ_SORT_ARG_SORT: AtomicU64 = AtomicU64::new(0);\nstatic MSI_APP_EQ_SORT_ARG_VAR: AtomicU64 = AtomicU64::new(0);\nstatic MSI_APP_EQ_SORT_ARG_CONST: AtomicU64 = AtomicU64::new(0);\nstatic MSI_APP_EQ_SORT_ARG_APP: AtomicU64 = AtomicU64::new(0);\nstatic MSI_APP_EQ_SORT_ARG_OTHER: AtomicU64 = AtomicU64::new(0);\nstatic MSI_APP_EQ_SORT_REPORTED: AtomicBool = AtomicBool::new(false);\n'
)

old = '''            if flag == Check {\n                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);\n                assert!(self.conv_types_at(depth, domain, arg_ty), "app arg def_eq failed");\n            }'''

new = '''            if flag == Check {\n                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);\n                let app_ty_ok = match (domain, arg_ty) {\n                    (Value::Sort { level: domain_level, .. }, Value::Sort { level: arg_level, .. })\n                        if domain_level == arg_level => {\n                            let total = MSI_APP_EQ_SORT_TOTAL.fetch_add(1, Ordering::Relaxed) + 1;\n                            match self.ctx.read_expr(arg) {\n                                Sort { .. } => { MSI_APP_EQ_SORT_ARG_SORT.fetch_add(1, Ordering::Relaxed); }\n                                Var { .. } => { MSI_APP_EQ_SORT_ARG_VAR.fetch_add(1, Ordering::Relaxed); }\n                                Const { .. } => { MSI_APP_EQ_SORT_ARG_CONST.fetch_add(1, Ordering::Relaxed); }\n                                App { .. } => { MSI_APP_EQ_SORT_ARG_APP.fetch_add(1, Ordering::Relaxed); }\n                                _ => { MSI_APP_EQ_SORT_ARG_OTHER.fetch_add(1, Ordering::Relaxed); }\n                            }\n                            if total >= 500_000 && !MSI_APP_EQ_SORT_REPORTED.swap(true, Ordering::Relaxed) {\n                                eprintln!(\n                                    "MSI_V34 total={} arg_sort={} arg_var={} arg_const={} arg_app={} arg_other={}",\n                                    MSI_APP_EQ_SORT_TOTAL.load(Ordering::Relaxed),\n                                    MSI_APP_EQ_SORT_ARG_SORT.load(Ordering::Relaxed),\n                                    MSI_APP_EQ_SORT_ARG_VAR.load(Ordering::Relaxed),\n                                    MSI_APP_EQ_SORT_ARG_CONST.load(Ordering::Relaxed),\n                                    MSI_APP_EQ_SORT_ARG_APP.load(Ordering::Relaxed),\n                                    MSI_APP_EQ_SORT_ARG_OTHER.load(Ordering::Relaxed),\n                                );\n                            }\n                            true\n                        }\n                    _ => self.conv_types_at(depth, domain, arg_ty),\n                };\n                assert!(app_ty_ok, "app arg def_eq failed");\n            }'''

if old not in s:
    raise SystemExit('target infer_app_v block not found')

s = s.replace(old, new, 1)
p.write_text(s)
print('applied MSI app producer census v34')
