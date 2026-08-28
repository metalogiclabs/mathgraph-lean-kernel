from pathlib import Path
p=Path('src/conv.rs')
s=p.read_text()
anchor='use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};\n'
ins=r'''use std::sync::atomic::{AtomicU64, Ordering};
static C_UNIFY: AtomicU64 = AtomicU64::new(0);
static C_PTR: AtomicU64 = AtomicU64::new(0);
static C_UF: AtomicU64 = AtomicU64::new(0);
static C_NEG: AtomicU64 = AtomicU64::new(0);
static C_PROBE_NEG: AtomicU64 = AtomicU64::new(0);
static C_NOCACHE: AtomicU64 = AtomicU64::new(0);
static C_DIRECT_OK: AtomicU64 = AtomicU64::new(0);
static C_COLD: AtomicU64 = AtomicU64::new(0);
static C_CACHEABLE: AtomicU64 = AtomicU64::new(0);

#[inline]
fn census_tick() {
    let n = C_UNIFY.fetch_add(1, Ordering::Relaxed) + 1;
    if n % 1_000_000 == 0 {
        eprintln!("MSI_CONV_RESIDUAL unify={} ptr={} cacheable={} uf={} neg={} probe_neg={} nocache={} direct_ok={} cold={}",
            n,
            C_PTR.load(Ordering::Relaxed), C_CACHEABLE.load(Ordering::Relaxed),
            C_UF.load(Ordering::Relaxed), C_NEG.load(Ordering::Relaxed), C_PROBE_NEG.load(Ordering::Relaxed),
            C_NOCACHE.load(Ordering::Relaxed), C_DIRECT_OK.load(Ordering::Relaxed), C_COLD.load(Ordering::Relaxed));
    }
}
'''
assert anchor in s
s=s.replace(anchor, anchor+ins,1)
old='''    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {\n        let x = self.force_thunk(depth, x);'''
new='''    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {\n        census_tick();\n        let x = self.force_thunk(depth, x);'''
assert old in s
s=s.replace(old,new,1)
old='''        if std::ptr::eq(x, y) {\n            return true;\n        }'''
new='''        if std::ptr::eq(x, y) {\n            C_PTR.fetch_add(1, Ordering::Relaxed);\n            return true;\n        }'''
assert old in s
s=s.replace(old,new,1)
old='''        if cacheable {\n            let xa = x as *const Value<'t> as usize;'''
new='''        if cacheable {\n            C_CACHEABLE.fetch_add(1, Ordering::Relaxed);\n            let xa = x as *const Value<'t> as usize;'''
assert old in s
s=s.replace(old,new,1)
old='''            if self.tc_cache.conv_uf.equiv(xa, ya) {\n                return true;\n            }'''
new='''            if self.tc_cache.conv_uf.equiv(xa, ya) {\n                C_UF.fetch_add(1, Ordering::Relaxed);\n                return true;\n            }'''
assert old in s
s=s.replace(old,new,1)
old='''                if self.tc_cache.conv_cache_neg.contains(&cache_key) {\n                    return false;\n                }'''
new='''                if self.tc_cache.conv_cache_neg.contains(&cache_key) {\n                    C_NEG.fetch_add(1, Ordering::Relaxed);\n                    return false;\n                }'''
assert old in s
s=s.replace(old,new,1)
old='''                if self.tc_cache.probe_depth > 0 && self.tc_cache.conv_cache_neg_probe.contains(&cache_key) {\n                    self.tc_cache.probe_exhausted = true;\n                    return false;\n                }'''
new='''                if self.tc_cache.probe_depth > 0 && self.tc_cache.conv_cache_neg_probe.contains(&cache_key) {\n                    C_PROBE_NEG.fetch_add(1, Ordering::Relaxed);\n                    self.tc_cache.probe_exhausted = true;\n                    return false;\n                }'''
assert old in s
s=s.replace(old,new,1)
old='''    fn unify_no_cache<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {\n        if self.tc_cache.probe_depth > 0 {'''
new='''    fn unify_no_cache<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {\n        C_NOCACHE.fetch_add(1, Ordering::Relaxed);\n        if self.tc_cache.probe_depth > 0 {'''
assert old in s
s=s.replace(old,new,1)
old='''        if self.unify_direct::<RIGID>(depth, t, t2) {\n            return true;\n        }\n        self.unify_cold::<RIGID>(depth, t, t2)'''
new='''        if self.unify_direct::<RIGID>(depth, t, t2) {\n            C_DIRECT_OK.fetch_add(1, Ordering::Relaxed);\n            return true;\n        }\n        C_COLD.fetch_add(1, Ordering::Relaxed);\n        self.unify_cold::<RIGID>(depth, t, t2)'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s)
print('applied MSI conversion residual v12')
