from pathlib import Path

p = Path('src/conv.rs')
s = p.read_text()
anchor = "use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};\n"
assert anchor in s
s = s.replace(anchor, anchor + r'''
use std::sync::atomic::{AtomicU64, Ordering};

static D_TOTAL: AtomicU64 = AtomicU64::new(0);
static D_RAW_SAMPLE: AtomicU64 = AtomicU64::new(0);
static D_RAW_DIGEST_EQ: AtomicU64 = AtomicU64::new(0);
static D_RAW_DIGEST_EQ_TRUE: AtomicU64 = AtomicU64::new(0);
static D_RAW_DIGEST_EQ_POSTPTR: AtomicU64 = AtomicU64::new(0);
static D_POST_SAMPLE: AtomicU64 = AtomicU64::new(0);
static D_POST_DIGEST_EQ: AtomicU64 = AtomicU64::new(0);
static D_POST_DIGEST_EQ_TRUE: AtomicU64 = AtomicU64::new(0);
static D_POST_DIGEST_NEQ: AtomicU64 = AtomicU64::new(0);
static D_POST_DIGEST_NEQ_TRUE: AtomicU64 = AtomicU64::new(0);

fn d_snapshot(n: u64) {
    eprintln!(
        "MSI_DIGEST_PREC total={} raw_sample={} raw_digest_eq={} raw_digest_eq_true={} raw_digest_eq_postptr={} post_sample={} post_digest_eq={} post_digest_eq_true={} post_digest_neq={} post_digest_neq_true={}",
        n,
        D_RAW_SAMPLE.load(Ordering::Relaxed),
        D_RAW_DIGEST_EQ.load(Ordering::Relaxed),
        D_RAW_DIGEST_EQ_TRUE.load(Ordering::Relaxed),
        D_RAW_DIGEST_EQ_POSTPTR.load(Ordering::Relaxed),
        D_POST_SAMPLE.load(Ordering::Relaxed),
        D_POST_DIGEST_EQ.load(Ordering::Relaxed),
        D_POST_DIGEST_EQ_TRUE.load(Ordering::Relaxed),
        D_POST_DIGEST_NEQ.load(Ordering::Relaxed),
        D_POST_DIGEST_NEQ_TRUE.load(Ordering::Relaxed),
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
        let n = D_TOTAL.fetch_add(1, Ordering::Relaxed) + 1;
        let sampled = (n & 63) == 0;
        let raw_distinct = !std::ptr::eq(x, y);
        let raw_digest_eq = if sampled && raw_distinct {
            D_RAW_SAMPLE.fetch_add(1, Ordering::Relaxed);
            let eq = x.digest() == y.digest();
            if eq { D_RAW_DIGEST_EQ.fetch_add(1, Ordering::Relaxed); }
            eq
        } else { false };

        let x = self.force_thunk(depth, x);
        let y = self.force_thunk(depth, y);
        if std::ptr::eq(x, y) {
            if raw_digest_eq {
                D_RAW_DIGEST_EQ_TRUE.fetch_add(1, Ordering::Relaxed);
                D_RAW_DIGEST_EQ_POSTPTR.fetch_add(1, Ordering::Relaxed);
            }
            if n % 1_000_000 == 0 { d_snapshot(n); }
            return true;
        }

        let post_digest_eq = if sampled {
            D_POST_SAMPLE.fetch_add(1, Ordering::Relaxed);
            let eq = x.digest() == y.digest();
            if eq { D_POST_DIGEST_EQ.fetch_add(1, Ordering::Relaxed); }
            else { D_POST_DIGEST_NEQ.fetch_add(1, Ordering::Relaxed); }
            eq
        } else { false };

        let r = self.unify_general::<RIGID>(depth, x, y);
        if sampled {
            if raw_digest_eq && r { D_RAW_DIGEST_EQ_TRUE.fetch_add(1, Ordering::Relaxed); }
            if post_digest_eq && r { D_POST_DIGEST_EQ_TRUE.fetch_add(1, Ordering::Relaxed); }
            if !post_digest_eq && r { D_POST_DIGEST_NEQ_TRUE.fetch_add(1, Ordering::Relaxed); }
        }
        if n % 1_000_000 == 0 { d_snapshot(n); }
        r
    }
'''
assert old in s
s = s.replace(old, new)
p.write_text(s)
print('applied MSI digest precision v18')
