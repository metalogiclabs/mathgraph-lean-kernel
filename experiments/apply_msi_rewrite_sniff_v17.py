from pathlib import Path

p = Path('src/conv.rs')
s = p.read_text()

anchor = "use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};\n"
assert anchor in s
s = s.replace(anchor, anchor + r'''
use std::sync::atomic::{AtomicU64, Ordering};

static S_TOTAL: AtomicU64 = AtomicU64::new(0);
static S_RAW_EQ: AtomicU64 = AtomicU64::new(0);
static S_POST_EQ_NEW: AtomicU64 = AtomicU64::new(0);
static S_FORCE_X_NOOP: AtomicU64 = AtomicU64::new(0);
static S_FORCE_Y_NOOP: AtomicU64 = AtomicU64::new(0);
static S_DIGEST_SAMPLE: AtomicU64 = AtomicU64::new(0);
static S_DIGEST_EQ_RAW: AtomicU64 = AtomicU64::new(0);
static S_DIGEST_POST_SAMPLE: AtomicU64 = AtomicU64::new(0);
static S_DIGEST_EQ_POST: AtomicU64 = AtomicU64::new(0);
static S_UF_HIT: AtomicU64 = AtomicU64::new(0);
static S_NEG_HIT: AtomicU64 = AtomicU64::new(0);
static S_DIRECT_OK: AtomicU64 = AtomicU64::new(0);
static S_COLD: AtomicU64 = AtomicU64::new(0);
static S_DIRECT_RIGID_BVAR: AtomicU64 = AtomicU64::new(0);
static S_DIRECT_NAMED: AtomicU64 = AtomicU64::new(0);
static S_DIRECT_RECQUOT: AtomicU64 = AtomicU64::new(0);
static S_DIRECT_PI: AtomicU64 = AtomicU64::new(0);
static S_DIRECT_LAM: AtomicU64 = AtomicU64::new(0);
static S_DIRECT_UNFOLD: AtomicU64 = AtomicU64::new(0);
static S_DIRECT_ATOMIC: AtomicU64 = AtomicU64::new(0);
static S_SPINE_CALL: AtomicU64 = AtomicU64::new(0);
static S_SPINE_PTR_EQ: AtomicU64 = AtomicU64::new(0);
static S_SPINE_APP: AtomicU64 = AtomicU64::new(0);
static S_SPINE_ARG_RAW_EQ: AtomicU64 = AtomicU64::new(0);
static S_SPINE_DIGEST_SAMPLE: AtomicU64 = AtomicU64::new(0);
static S_SPINE_DIGEST_EQ: AtomicU64 = AtomicU64::new(0);
static S_PROOF_SKIP: AtomicU64 = AtomicU64::new(0);
static S_SIG_CALL: AtomicU64 = AtomicU64::new(0);
static S_SIG_MASK: AtomicU64 = AtomicU64::new(0);

fn sniff_snapshot(n: u64) {
    eprintln!(
        "MSI_SNIFF total={} raw_eq={} post_eq_new={} force_x_noop={} force_y_noop={} digest_sample={} digest_eq_raw={} digest_post_sample={} digest_eq_post={} uf_hit={} neg_hit={} direct_ok={} cold={} direct_rigid_bvar={} direct_named={} direct_recquot={} direct_pi={} direct_lam={} direct_unfold={} direct_atomic={} spine_call={} spine_ptr_eq={} spine_app={} spine_arg_raw_eq={} spine_digest_sample={} spine_digest_eq={} proof_skip={} sig_call={} sig_mask={}",
        n,
        S_RAW_EQ.load(Ordering::Relaxed), S_POST_EQ_NEW.load(Ordering::Relaxed),
        S_FORCE_X_NOOP.load(Ordering::Relaxed), S_FORCE_Y_NOOP.load(Ordering::Relaxed),
        S_DIGEST_SAMPLE.load(Ordering::Relaxed), S_DIGEST_EQ_RAW.load(Ordering::Relaxed),
        S_DIGEST_POST_SAMPLE.load(Ordering::Relaxed), S_DIGEST_EQ_POST.load(Ordering::Relaxed),
        S_UF_HIT.load(Ordering::Relaxed), S_NEG_HIT.load(Ordering::Relaxed),
        S_DIRECT_OK.load(Ordering::Relaxed), S_COLD.load(Ordering::Relaxed),
        S_DIRECT_RIGID_BVAR.load(Ordering::Relaxed), S_DIRECT_NAMED.load(Ordering::Relaxed),
        S_DIRECT_RECQUOT.load(Ordering::Relaxed), S_DIRECT_PI.load(Ordering::Relaxed),
        S_DIRECT_LAM.load(Ordering::Relaxed), S_DIRECT_UNFOLD.load(Ordering::Relaxed),
        S_DIRECT_ATOMIC.load(Ordering::Relaxed),
        S_SPINE_CALL.load(Ordering::Relaxed), S_SPINE_PTR_EQ.load(Ordering::Relaxed),
        S_SPINE_APP.load(Ordering::Relaxed), S_SPINE_ARG_RAW_EQ.load(Ordering::Relaxed),
        S_SPINE_DIGEST_SAMPLE.load(Ordering::Relaxed), S_SPINE_DIGEST_EQ.load(Ordering::Relaxed),
        S_PROOF_SKIP.load(Ordering::Relaxed), S_SIG_CALL.load(Ordering::Relaxed), S_SIG_MASK.load(Ordering::Relaxed)
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
        let n = S_TOTAL.fetch_add(1, Ordering::Relaxed) + 1;
        let raw_eq = std::ptr::eq(x, y);
        if raw_eq { S_RAW_EQ.fetch_add(1, Ordering::Relaxed); }
        if !raw_eq && (n & 63) == 0 {
            S_DIGEST_SAMPLE.fetch_add(1, Ordering::Relaxed);
            if x.digest() == y.digest() { S_DIGEST_EQ_RAW.fetch_add(1, Ordering::Relaxed); }
        }
        let ox = x;
        let oy = y;
        let x = self.force_thunk(depth, x);
        let y = self.force_thunk(depth, y);
        if std::ptr::eq(ox, x) { S_FORCE_X_NOOP.fetch_add(1, Ordering::Relaxed); }
        if std::ptr::eq(oy, y) { S_FORCE_Y_NOOP.fetch_add(1, Ordering::Relaxed); }
        if std::ptr::eq(x, y) {
            if !raw_eq { S_POST_EQ_NEW.fetch_add(1, Ordering::Relaxed); }
            if n % 1_000_000 == 0 { sniff_snapshot(n); }
            return true;
        }
        if (n & 63) == 0 {
            S_DIGEST_POST_SAMPLE.fetch_add(1, Ordering::Relaxed);
            if x.digest() == y.digest() { S_DIGEST_EQ_POST.fetch_add(1, Ordering::Relaxed); }
        }
        let r = self.unify_general::<RIGID>(depth, x, y);
        if n % 1_000_000 == 0 { sniff_snapshot(n); }
        r
    }
'''
assert old in s
s = s.replace(old, new)

s = s.replace(
"            if self.tc_cache.conv_uf.equiv(xa, ya) {\n                return true;\n            }",
"            if self.tc_cache.conv_uf.equiv(xa, ya) {\n                S_UF_HIT.fetch_add(1, Ordering::Relaxed);\n                return true;\n            }"
)
s = s.replace(
"                if self.tc_cache.conv_cache_neg.contains(&cache_key) {\n                    return false;\n                }",
"                if self.tc_cache.conv_cache_neg.contains(&cache_key) {\n                    S_NEG_HIT.fetch_add(1, Ordering::Relaxed);\n                    return false;\n                }"
)

old = r'''        if let Some(r) = self.conv_nat::<RIGID>(depth, t, t2) {
            return r;
        }
        if self.unify_direct::<RIGID>(depth, t, t2) {
            return true;
        }
        self.unify_cold::<RIGID>(depth, t, t2)
'''
new = r'''        if let Some(r) = self.conv_nat::<RIGID>(depth, t, t2) {
            if r { S_DIRECT_OK.fetch_add(1, Ordering::Relaxed); }
            return r;
        }
        if self.unify_direct::<RIGID>(depth, t, t2) {
            S_DIRECT_OK.fetch_add(1, Ordering::Relaxed);
            return true;
        }
        S_COLD.fetch_add(1, Ordering::Relaxed);
        self.unify_cold::<RIGID>(depth, t, t2)
'''
assert old in s
s = s.replace(old, new)

# Direct constructor-family exposure counts.
s = s.replace(
"            (Value::Sort { level: lx , .. }, Value::Sort { level: ly , .. }) => self.ctx.eq_antisymm(*lx, *ly),",
"            (Value::Sort { level: lx , .. }, Value::Sort { level: ly , .. }) => { S_DIRECT_ATOMIC.fetch_add(1, Ordering::Relaxed); self.ctx.eq_antisymm(*lx, *ly) },"
)
s = s.replace(
"            (Value::NatLit { ptr: px , .. }, Value::NatLit { ptr: py , .. }) => px == py,",
"            (Value::NatLit { ptr: px , .. }, Value::NatLit { ptr: py , .. }) => { S_DIRECT_ATOMIC.fetch_add(1, Ordering::Relaxed); px == py },"
)
s = s.replace(
"            (Value::StrLit { ptr: px , .. }, Value::StrLit { ptr: py , .. }) => px == py,",
"            (Value::StrLit { ptr: px , .. }, Value::StrLit { ptr: py , .. }) => { S_DIRECT_ATOMIC.fetch_add(1, Ordering::Relaxed); px == py },"
)
s = s.replace(
"            (Value::Rigid { head: hx, spine: sx, .. }, Value::Rigid { head: hy, spine: sy, .. }) if rigid_head_eq(*hx, *hy) =>\n                self.unify_spine::<RIGID>(depth, sx, sy, Sig::ALL_RELEVANT, 0),",
"            (Value::Rigid { head: hx, spine: sx, .. }, Value::Rigid { head: hy, spine: sy, .. }) if rigid_head_eq(*hx, *hy) => {\n                S_DIRECT_RIGID_BVAR.fetch_add(1, Ordering::Relaxed);\n                self.unify_spine::<RIGID>(depth, sx, sy, Sig::ALL_RELEVANT, 0)\n            },"
)
# Named rigid families share head/signature/spine machinery.
for tag in ["Ctor", "Inductive", "Axiom"]:
    needle = f"            ) if nx == ny && self.ctx.eq_antisymm_many(*lx, *ly) => {{\n                let (sig, limit) = self.head_spine_sig(*nx, *lx, sx, sy);"
    repl = f"            ) if nx == ny && self.ctx.eq_antisymm_many(*lx, *ly) => {{\n                S_DIRECT_NAMED.fetch_add(1, Ordering::Relaxed);\n                let (sig, limit) = self.head_spine_sig(*nx, *lx, sx, sy);"
    if needle in s:
        s = s.replace(needle, repl, 1)

# Count recursor/quotient pair branch entries by injecting after heads_match construction.
s = s.replace(
"                let heads_match = nx == ny && self.ctx.eq_antisymm_many(lx, ly);\n                self.unify_iota::<RIGID>(depth, t, t2, heads_match, nx, lx, sx, sy)",
"                S_DIRECT_RECQUOT.fetch_add(1, Ordering::Relaxed);\n                let heads_match = nx == ny && self.ctx.eq_antisymm_many(lx, ly);\n                self.unify_iota::<RIGID>(depth, t, t2, heads_match, nx, lx, sx, sy)"
)
s = s.replace(
"            (Value::Pi { domain: dx, body: bx, .. }, Value::Pi { domain: dy, body: by, .. }) => {\n",
"            (Value::Pi { domain: dx, body: bx, .. }, Value::Pi { domain: dy, body: by, .. }) => {\n                S_DIRECT_PI.fetch_add(1, Ordering::Relaxed);\n"
)
s = s.replace(
"            (Value::Lam { body: bx, .. }, Value::Lam { body: by, .. }) => {\n",
"            (Value::Lam { body: bx, .. }, Value::Lam { body: by, .. }) => {\n                S_DIRECT_LAM.fetch_add(1, Ordering::Relaxed);\n"
)
s = s.replace(
"            ) => {\n                let heads_match = nx == ny && self.ctx.eq_antisymm_many(*lx, *ly);\n                let (nx, ny, lx) = (*nx, *ny, *lx);",
"            ) => {\n                S_DIRECT_UNFOLD.fetch_add(1, Ordering::Relaxed);\n                let heads_match = nx == ny && self.ctx.eq_antisymm_many(*lx, *ly);\n                let (nx, ny, lx) = (*nx, *ny, *lx);",
1)

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
        S_SIG_CALL.fetch_add(1, Ordering::Relaxed);
        let sig = self.sig_of(name, levels);
        if !sig.masks_any_arg() {
            return (Sig::ALL_RELEVANT, 0);
        }
        S_SIG_MASK.fetch_add(1, Ordering::Relaxed);
        (sig, app_prefix_len(sx).min(app_prefix_len(sy)))
    }
'''
assert old in s
s = s.replace(old, new)

old = r'''    fn unify_spine<const RIGID: bool>(&mut self, depth: u32, sx: S<'t>, sy: S<'t>, sig: Sig, limit: u32) -> bool {
        if std::ptr::eq(sx, sy) {
            return true;
        }
'''
new = r'''    fn unify_spine<const RIGID: bool>(&mut self, depth: u32, sx: S<'t>, sy: S<'t>, sig: Sig, limit: u32) -> bool {
        S_SPINE_CALL.fetch_add(1, Ordering::Relaxed);
        if std::ptr::eq(sx, sy) {
            S_SPINE_PTR_EQ.fetch_add(1, Ordering::Relaxed);
            return true;
        }
'''
assert old in s
s = s.replace(old, new)

s = s.replace(
"                    (ElimView::App(va), ElimView::App(vb)) => {\n                        let idx = pa.len();",
"                    (ElimView::App(va), ElimView::App(vb)) => {\n                        S_SPINE_APP.fetch_add(1, Ordering::Relaxed);\n                        let arg_raw_eq = std::ptr::eq(va, vb);\n                        if arg_raw_eq { S_SPINE_ARG_RAW_EQ.fetch_add(1, Ordering::Relaxed); }\n                        let sn = S_SPINE_APP.load(Ordering::Relaxed);\n                        if !arg_raw_eq && (sn & 63) == 0 {\n                            S_SPINE_DIGEST_SAMPLE.fetch_add(1, Ordering::Relaxed);\n                            if va.digest() == vb.digest() { S_SPINE_DIGEST_EQ.fetch_add(1, Ordering::Relaxed); }\n                        }\n                        let idx = pa.len();"
)
s = s.replace(
"                        if idx < limit && sig.arg_is_proof(idx) {\n                            return true;\n                        }",
"                        if idx < limit && sig.arg_is_proof(idx) {\n                            S_PROOF_SKIP.fetch_add(1, Ordering::Relaxed);\n                            return true;\n                        }"
)

p.write_text(s)
print('applied MSI rewrite sniff v17')
