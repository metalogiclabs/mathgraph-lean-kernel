from pathlib import Path

p = Path('src/infer.rs')
s = p.read_text()

s = s.replace(
    'use InferFlag::*;\n',
    '''use InferFlag::*;\nuse std::cell::Cell;\nuse std::sync::atomic::{AtomicBool, AtomicU64, Ordering};\n\nthread_local! {\n    static MSI_V35_LAST_ORIGIN: Cell<u8> = const { Cell::new(0) };\n}\n\nconst MSI_V35_VAR: u8 = 1;\nconst MSI_V35_SORT: u8 = 2;\nconst MSI_V35_CONST: u8 = 3;\nconst MSI_V35_LITERAL: u8 = 4;\nconst MSI_V35_CACHE: u8 = 5;\nconst MSI_V35_APP: u8 = 6;\nconst MSI_V35_LAMBDA: u8 = 7;\nconst MSI_V35_PI: u8 = 8;\nconst MSI_V35_LET: u8 = 9;\nconst MSI_V35_PROJ: u8 = 10;\n\nstatic MSI_V35_TOTAL: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V35_VAR_N: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V35_SORT_N: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V35_CONST_N: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V35_LITERAL_N: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V35_CACHE_N: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V35_APP_N: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V35_OTHER_N: AtomicU64 = AtomicU64::new(0);\nstatic MSI_V35_REPORTED: AtomicBool = AtomicBool::new(false);\n\n#[inline]\nfn msi_v35_set_origin(o: u8) { MSI_V35_LAST_ORIGIN.with(|x| x.set(o)); }\n'''
)

# Direct return paths: record the provenance of the top-level infer_value result.
s = s.replace(
    'Var { dbj_idx, .. } => return ctx.lookup(dbj_idx).expect("loose bvar in infer"),',
    'Var { dbj_idx, .. } => { let r = ctx.lookup(dbj_idx).expect("loose bvar in infer"); msi_v35_set_origin(MSI_V35_VAR); return r },'
)
s = s.replace(
    'return value::mk_sort(self.arena, sc);',
    'let r = value::mk_sort(self.arena, sc); msi_v35_set_origin(MSI_V35_SORT); return r;',
    1,
)
s = s.replace(
    'return self.const_head_type(name, levels);',
    'let r = self.const_head_type(name, levels); msi_v35_set_origin(MSI_V35_CONST); return r;',
    1,
)
s = s.replace(
    'return self.lit_inductive_type(self.ctx.export_file.name_cache.nat);',
    'let r = self.lit_inductive_type(self.ctx.export_file.name_cache.nat); msi_v35_set_origin(MSI_V35_LITERAL); return r;',
    1,
)
s = s.replace(
    'return self.lit_inductive_type(self.ctx.export_file.name_cache.string);',
    'let r = self.lit_inductive_type(self.ctx.export_file.name_cache.string); msi_v35_set_origin(MSI_V35_LITERAL); return r;',
    1,
)

old_cache = '''        if let Some(cached) = self.tc_cache.type_cache.get(&key).copied() {\n            if flag == InferOnly || cached.checked_under == scope {\n                return cached.result;\n            }\n        }'''
new_cache = '''        if let Some(cached) = self.tc_cache.type_cache.get(&key).copied() {\n            if flag == InferOnly || cached.checked_under == scope {\n                msi_v35_set_origin(MSI_V35_CACHE);\n                return cached.result;\n            }\n        }'''
if old_cache not in s:
    raise SystemExit('cache block not found')
s = s.replace(old_cache, new_cache, 1)

# Record the semantic producer class after recursive/composite inference completes.
old_tail = '''        self.tc_cache.type_cache.insert(key, CachedType { result: r, checked_under });\n        r\n    }'''
new_tail = '''        self.tc_cache.type_cache.insert(key, CachedType { result: r, checked_under });\n        let origin = match self.ctx.read_expr(e) {\n            App { .. } => MSI_V35_APP,\n            Lambda { .. } => MSI_V35_LAMBDA,\n            Pi { .. } => MSI_V35_PI,\n            Let { .. } => MSI_V35_LET,\n            Proj { .. } => MSI_V35_PROJ,\n            _ => 0,\n        };\n        msi_v35_set_origin(origin);\n        r\n    }'''
if old_tail not in s:
    raise SystemExit('infer_value tail not found')
s = s.replace(old_tail, new_tail, 1)

old_app = '''            if flag == Check {\n                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);\n                assert!(self.conv_types_at(depth, domain, arg_ty), "app arg def_eq failed");\n            }'''
new_app = '''            if flag == Check {\n                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);\n                let arg_origin = MSI_V35_LAST_ORIGIN.with(|x| x.get());\n                let app_ty_ok = match (domain, arg_ty) {\n                    (Value::Sort { level: domain_level, .. }, Value::Sort { level: arg_level, .. })\n                        if domain_level == arg_level => {\n                            let total = MSI_V35_TOTAL.fetch_add(1, Ordering::Relaxed) + 1;\n                            match arg_origin {\n                                MSI_V35_VAR => { MSI_V35_VAR_N.fetch_add(1, Ordering::Relaxed); }\n                                MSI_V35_SORT => { MSI_V35_SORT_N.fetch_add(1, Ordering::Relaxed); }\n                                MSI_V35_CONST => { MSI_V35_CONST_N.fetch_add(1, Ordering::Relaxed); }\n                                MSI_V35_LITERAL => { MSI_V35_LITERAL_N.fetch_add(1, Ordering::Relaxed); }\n                                MSI_V35_CACHE => { MSI_V35_CACHE_N.fetch_add(1, Ordering::Relaxed); }\n                                MSI_V35_APP => { MSI_V35_APP_N.fetch_add(1, Ordering::Relaxed); }\n                                _ => { MSI_V35_OTHER_N.fetch_add(1, Ordering::Relaxed); }\n                            }\n                            if total >= 500_000 && !MSI_V35_REPORTED.swap(true, Ordering::Relaxed) {\n                                eprintln!(\n                                    "MSI_V35 total={} var={} sort={} const={} literal={} cache={} app={} other={}",\n                                    MSI_V35_TOTAL.load(Ordering::Relaxed),\n                                    MSI_V35_VAR_N.load(Ordering::Relaxed),\n                                    MSI_V35_SORT_N.load(Ordering::Relaxed),\n                                    MSI_V35_CONST_N.load(Ordering::Relaxed),\n                                    MSI_V35_LITERAL_N.load(Ordering::Relaxed),\n                                    MSI_V35_CACHE_N.load(Ordering::Relaxed),\n                                    MSI_V35_APP_N.load(Ordering::Relaxed),\n                                    MSI_V35_OTHER_N.load(Ordering::Relaxed),\n                                );\n                            }\n                            true\n                        }\n                    _ => self.conv_types_at(depth, domain, arg_ty),\n                };\n                assert!(app_ty_ok, "app arg def_eq failed");\n            }'''
if old_app not in s:
    raise SystemExit('infer_app_v check block not found')
s = s.replace(old_app, new_app, 1)

p.write_text(s)
print('applied MSI Sort information-lifetime trace v35')
