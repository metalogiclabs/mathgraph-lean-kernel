from pathlib import Path

p=Path('src/conv.rs')
s=p.read_text()
anchor="use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};\n"
assert anchor in s
s=s.replace(anchor, anchor+r'''
use std::sync::atomic::{AtomicU64, Ordering};

static MSI_ORIGIN_TOTAL: AtomicU64 = AtomicU64::new(0);
static MSI_ORIGIN_CONV_TYPES: AtomicU64 = AtomicU64::new(0);
static MSI_ORIGIN_DEF_EQ: AtomicU64 = AtomicU64::new(0);
static MSI_ORIGIN_PI_DOMAIN: AtomicU64 = AtomicU64::new(0);
static MSI_ORIGIN_PI_BODY: AtomicU64 = AtomicU64::new(0);
static MSI_ORIGIN_LAM_BODY: AtomicU64 = AtomicU64::new(0);
static MSI_ORIGIN_SPINE: AtomicU64 = AtomicU64::new(0);
static MSI_ORIGIN_PROBE: AtomicU64 = AtomicU64::new(0);
static MSI_ORIGIN_REWRITE: AtomicU64 = AtomicU64::new(0);
static MSI_ORIGIN_ETA: AtomicU64 = AtomicU64::new(0);

fn msi_origin_hit(origin: u8, x: &Value<'_>, y: &Value<'_>) {
    if let (Value::Sort { level: lx, .. }, Value::Sort { level: ly, .. }) = (x, y) {
        if lx == ly {
            match origin {
                0 => { MSI_ORIGIN_CONV_TYPES.fetch_add(1, Ordering::Relaxed); }
                1 => { MSI_ORIGIN_DEF_EQ.fetch_add(1, Ordering::Relaxed); }
                2 => { MSI_ORIGIN_PI_DOMAIN.fetch_add(1, Ordering::Relaxed); }
                3 => { MSI_ORIGIN_PI_BODY.fetch_add(1, Ordering::Relaxed); }
                4 => { MSI_ORIGIN_LAM_BODY.fetch_add(1, Ordering::Relaxed); }
                5 => { MSI_ORIGIN_SPINE.fetch_add(1, Ordering::Relaxed); }
                6 => { MSI_ORIGIN_PROBE.fetch_add(1, Ordering::Relaxed); }
                7 => { MSI_ORIGIN_REWRITE.fetch_add(1, Ordering::Relaxed); }
                8 => { MSI_ORIGIN_ETA.fetch_add(1, Ordering::Relaxed); }
                _ => {}
            }
        }
    }
    let n=MSI_ORIGIN_TOTAL.fetch_add(1, Ordering::Relaxed)+1;
    if n % 500_000 == 0 {
        eprintln!("MSI_ORIGIN total={} conv_types={} def_eq={} pi_domain={} pi_body={} lam_body={} spine={} probe={} rewrite={} eta={}",
            n,
            MSI_ORIGIN_CONV_TYPES.load(Ordering::Relaxed),
            MSI_ORIGIN_DEF_EQ.load(Ordering::Relaxed),
            MSI_ORIGIN_PI_DOMAIN.load(Ordering::Relaxed),
            MSI_ORIGIN_PI_BODY.load(Ordering::Relaxed),
            MSI_ORIGIN_LAM_BODY.load(Ordering::Relaxed),
            MSI_ORIGIN_SPINE.load(Ordering::Relaxed),
            MSI_ORIGIN_PROBE.load(Ordering::Relaxed),
            MSI_ORIGIN_REWRITE.load(Ordering::Relaxed),
            MSI_ORIGIN_ETA.load(Ordering::Relaxed));
    }
}
''')

anchor2=r'''    #[inline]
    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
        let x = self.force_thunk(depth, x);
        let y = self.force_thunk(depth, y);
        if std::ptr::eq(x, y) {
            return true;
        }
        self.unify_general::<RIGID>(depth, x, y)
    }
'''
assert anchor2 in s
new2=anchor2+r'''
    #[inline]
    fn unify_from<const RIGID: bool>(&mut self, origin: u8, depth: u32, x: V<'t>, y: V<'t>) -> bool {
        msi_origin_hit(origin, x, y);
        self.unify::<RIGID>(depth, x, y)
    }
'''
s=s.replace(anchor2,new2)

s=s.replace('self.unbudgeted(|s| s.unify::<true>(depth, a, b))','self.unbudgeted(|s| s.unify_from::<true>(0, depth, a, b))')
s=s.replace('self.unbudgeted(|s| s.try_proof_irrel_at(depth, vx, vy) || s.unify::<true>(depth, vx, vy))','self.unbudgeted(|s| s.try_proof_irrel_at(depth, vx, vy) || s.unify_from::<true>(1, depth, vx, vy))')

# Exact structurally-known recursive edges.
s=s.replace('if !self.unify::<RIGID>(depth, dx, dy) {','if !self.unify_from::<RIGID>(2, depth, dx, dy) {')
s=s.replace('self.unify::<RIGID>(depth + 1, vx, vy)\n            }\n\n            (Value::Lam', 'self.unify_from::<RIGID>(3, depth + 1, vx, vy)\n            }\n\n            (Value::Lam')
s=s.replace('self.unify::<RIGID>(depth + 1, vx, vy)\n            }\n\n            (\n                Value::Unfold', 'self.unify_from::<RIGID>(4, depth + 1, vx, vy)\n            }\n\n            (\n                Value::Unfold')
s=s.replace('self.unify::<RIGID>(depth, va, vb)','self.unify_from::<RIGID>(5, depth, va, vb)')
s=s.replace('let ok = self.unify::<true>(depth, va, vb);','let ok = self.unify_from::<true>(6, depth, va, vb);')

# Any conversion recursion caused by unfold/iota normalization is tagged rewrite.
for old in [
    'self.unify::<true>(depth, t, v2)', 'self.unify::<true>(depth, v1, t2)',
    'self.unify::<true>(depth, t, f2)', 'self.unify::<true>(depth, f1, t2)',
    'self.unify::<true>(depth, f1, f2)', 'self.unify::<true>(depth, v1, v2)'
]:
    s=s.replace(old, old.replace('self.unify::<true>(', 'self.unify_from::<true>(7, '))

# Eta expansion recursive comparisons.
s=s.replace('return self.unify::<true>(depth + 1, lhs, rhs);','return self.unify_from::<true>(8, depth + 1, lhs, rhs);')

p.write_text(s)
print('applied MSI compiled-interface origin census v29')
