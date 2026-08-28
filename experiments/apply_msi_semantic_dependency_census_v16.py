from pathlib import Path

p = Path('src/conv.rs')
s = p.read_text()

anchor = "use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};\n"
assert anchor in s
s = s.replace(anchor, anchor + r'''
use std::sync::atomic::{AtomicU64, Ordering};

static MSI_TOTAL: AtomicU64 = AtomicU64::new(0);
static MSI_RAW_EQ: AtomicU64 = AtomicU64::new(0);
static MSI_POST_EQ: AtomicU64 = AtomicU64::new(0);
static MSI_POST_EQ_NEW: AtomicU64 = AtomicU64::new(0);
static MSI_CACHEABLE: AtomicU64 = AtomicU64::new(0);
static MSI_UF_HIT: AtomicU64 = AtomicU64::new(0);
static MSI_NEG_HIT: AtomicU64 = AtomicU64::new(0);
static MSI_NO_CACHE: AtomicU64 = AtomicU64::new(0);
static MSI_DIRECT_OK: AtomicU64 = AtomicU64::new(0);
static MSI_COLD: AtomicU64 = AtomicU64::new(0);
static MSI_SIG_CALL: AtomicU64 = AtomicU64::new(0);
static MSI_SIG_MASK: AtomicU64 = AtomicU64::new(0);
static MSI_SPINE_CALL: AtomicU64 = AtomicU64::new(0);
static MSI_SPINE_PTR_EQ: AtomicU64 = AtomicU64::new(0);
static MSI_SPINE_NODE: AtomicU64 = AtomicU64::new(0);
static MSI_SPINE_APP: AtomicU64 = AtomicU64::new(0);
static MSI_SPINE_ARG_RAW_EQ: AtomicU64 = AtomicU64::new(0);
static MSI_SPINE_PROOF_SKIP: AtomicU64 = AtomicU64::new(0);

fn msi_snapshot(n: u64) {
    eprintln!(
        "MSI_DEP total={} raw_eq={} post_eq={} post_eq_new={} cacheable={} uf_hit={} neg_hit={} no_cache={} direct_ok={} cold={} sig_call={} sig_mask={} spine_call={} spine_ptr_eq={} spine_node={} spine_app={} spine_arg_raw_eq={} spine_proof_skip={}",
        n,
        MSI_RAW_EQ.load(Ordering::Relaxed),
        MSI_POST_EQ.load(Ordering::Relaxed),
        MSI_POST_EQ_NEW.load(Ordering::Relaxed),
        MSI_CACHEABLE.load(Ordering::Relaxed),
        MSI_UF_HIT.load(Ordering::Relaxed),
        MSI_NEG_HIT.load(Ordering::Relaxed),
        MSI_NO_CACHE.load(Ordering::Relaxed),
        MSI_DIRECT_OK.load(Ordering::Relaxed),
        MSI_COLD.load(Ordering::Relaxed),
        MSI_SIG_CALL.load(Ordering::Relaxed),
        MSI_SIG_MASK.load(Ordering::Relaxed),
        MSI_SPINE_CALL.load(Ordering::Relaxed),
        MSI_SPINE_PTR_EQ.load(Ordering::Relaxed),
        MSI_SPINE_NODE.load(Ordering::Relaxed),
        MSI_SPINE_APP.load(Ordering::Relaxed),
        MSI_SPINE_ARG_RAW_EQ.load(Ordering::Relaxed),
        MSI_SPINE_PROOF_SKIP.load(Ordering::Relaxed),
    );
}
''')

old = r'''    #[inline]
    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
        let x = self.force_thunk(depth, x);
        let y = self.force_thunk(depth, y);
        if std::ptr::eq(x, y) {
            return true;
        }
        self.unify_general::<RIGID>(depth, x, y)
    }
'''
new = r'''    #[inline]
    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
        let n = MSI_TOTAL.fetch_add(1, Ordering::Relaxed) + 1;
        let raw_eq = std::ptr::eq(x, y);
        if raw_eq {
            MSI_RAW_EQ.fetch_add(1, Ordering::Relaxed);
        }
        let x = self.force_thunk(depth, x);
        let y = self.force_thunk(depth, y);
        if std::ptr::eq(x, y) {
            MSI_POST_EQ.fetch_add(1, Ordering::Relaxed);
            if !raw_eq {
                MSI_POST_EQ_NEW.fetch_add(1, Ordering::Relaxed);
            }
            if n % 1_000_000 == 0 { msi_snapshot(n); }
            return true;
        }
        let r = self.unify_general::<RIGID>(depth, x, y);
        if n % 1_000_000 == 0 { msi_snapshot(n); }
        r
    }
'''
assert old in s
s = s.replace(old, new)

s = s.replace(
"        if cacheable {\n            let xa = x as *const Value<'t> as usize;",
"        if cacheable {\n            MSI_CACHEABLE.fetch_add(1, Ordering::Relaxed);\n            let xa = x as *const Value<'t> as usize;"
)
s = s.replace(
"            if self.tc_cache.conv_uf.equiv(xa, ya) {\n                return true;\n            }",
"            if self.tc_cache.conv_uf.equiv(xa, ya) {\n                MSI_UF_HIT.fetch_add(1, Ordering::Relaxed);\n                return true;\n            }"
)
s = s.replace(
"                if self.tc_cache.conv_cache_neg.contains(&cache_key) {\n                    return false;\n                }",
"                if self.tc_cache.conv_cache_neg.contains(&cache_key) {\n                    MSI_NEG_HIT.fetch_add(1, Ordering::Relaxed);\n                    return false;\n                }"
)

old = r'''        if let Some(r) = self.conv_nat::<RIGID>(depth, t, t2) {
            return r;
        }
        if self.unify_direct::<RIGID>(depth, t, t2) {
            return true;
        }
        self.unify_cold::<RIGID>(depth, t, t2)
'''
new = r'''        MSI_NO_CACHE.fetch_add(1, Ordering::Relaxed);
        if let Some(r) = self.conv_nat::<RIGID>(depth, t, t2) {
            if r { MSI_DIRECT_OK.fetch_add(1, Ordering::Relaxed); }
            return r;
        }
        if self.unify_direct::<RIGID>(depth, t, t2) {
            MSI_DIRECT_OK.fetch_add(1, Ordering::Relaxed);
            return true;
        }
        MSI_COLD.fetch_add(1, Ordering::Relaxed);
        self.unify_cold::<RIGID>(depth, t, t2)
'''
assert old in s
s = s.replace(old, new)

old = r'''    #[inline]
    fn head_spine_sig(&mut self, name: NamePtr<'t>, levels: LevelsPtr<'t>, sx: S<'t>, sy: S<'t>) -> (Sig, u32) {
        let sig = self.sig_of(name, levels);
        if !sig.masks_any_arg() {
            return (Sig::ALL_RELEVANT, 0);
        }
        (sig, app_prefix_len(sx).min(app_prefix_len(sy)))
    }
'''
new = r'''    #[inline]
    fn head_spine_sig(&mut self, name: NamePtr<'t>, levels: LevelsPtr<'t>, sx: S<'t>, sy: S<'t>) -> (Sig, u32) {
        MSI_SIG_CALL.fetch_add(1, Ordering::Relaxed);
        let sig = self.sig_of(name, levels);
        if !sig.masks_any_arg() {
            return (Sig::ALL_RELEVANT, 0);
        }
        MSI_SIG_MASK.fetch_add(1, Ordering::Relaxed);
        (sig, app_prefix_len(sx).min(app_prefix_len(sy)))
    }
'''
assert old in s
s = s.replace(old, new)

old = r'''    fn unify_spine<const RIGID: bool>(&mut self, depth: u32, sx: S<'t>, sy: S<'t>, sig: Sig, limit: u32) -> bool {
        if std::ptr::eq(sx, sy) {
            return true;
        }
        match (sx, sy) {
'''
new = r'''    fn unify_spine<const RIGID: bool>(&mut self, depth: u32, sx: S<'t>, sy: S<'t>, sig: Sig, limit: u32) -> bool {
        MSI_SPINE_CALL.fetch_add(1, Ordering::Relaxed);
        if std::ptr::eq(sx, sy) {
            MSI_SPINE_PTR_EQ.fetch_add(1, Ordering::Relaxed);
            return true;
        }
        match (sx, sy) {
'''
assert old in s
s = s.replace(old, new)

s = s.replace(
"            (Spine::Snoc { prev: pa, elim: ea, .. }, Spine::Snoc { prev: pb, elim: eb, .. }) => {\n                if !self.unify_spine::<RIGID>(depth, pa, pb, sig, limit) {",
"            (Spine::Snoc { prev: pa, elim: ea, .. }, Spine::Snoc { prev: pb, elim: eb, .. }) => {\n                MSI_SPINE_NODE.fetch_add(1, Ordering::Relaxed);\n                if !self.unify_spine::<RIGID>(depth, pa, pb, sig, limit) {"
)
s = s.replace(
"                    (ElimView::App(va), ElimView::App(vb)) => {\n                        let idx = pa.len();\n                        if idx < limit && sig.arg_is_proof(idx) {\n                            return true;\n                        }\n                        self.unify::<RIGID>(depth, va, vb)",
"                    (ElimView::App(va), ElimView::App(vb)) => {\n                        MSI_SPINE_APP.fetch_add(1, Ordering::Relaxed);\n                        if std::ptr::eq(va, vb) { MSI_SPINE_ARG_RAW_EQ.fetch_add(1, Ordering::Relaxed); }\n                        let idx = pa.len();\n                        if idx < limit && sig.arg_is_proof(idx) {\n                            MSI_SPINE_PROOF_SKIP.fetch_add(1, Ordering::Relaxed);\n                            return true;\n                        }\n                        self.unify::<RIGID>(depth, va, vb)"
)

p.write_text(s)
print('applied MSI semantic dependency census v16')
