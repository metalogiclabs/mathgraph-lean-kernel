from pathlib import Path

# Expose whether a digest has already been computed, without forcing computation.
p = Path('src/value.rs')
s = p.read_text()
old = r'''    #[inline]
    pub fn digest(&self) -> u64 {
        let cell = self.key_cell();
        let k = cell.get();
        if k & KEY_PRESENT != 0 {
            return k;
        }
        let d = self.compute_key();
        cell.set(d);
        d
    }
'''
new = r'''    #[inline]
    pub fn digest(&self) -> u64 {
        let cell = self.key_cell();
        let k = cell.get();
        if k & KEY_PRESENT != 0 {
            return k;
        }
        let d = self.compute_key();
        cell.set(d);
        d
    }

    #[inline]
    pub fn cached_digest(&self) -> Option<u64> {
        let k = self.key_cell().get();
        if k & KEY_PRESENT != 0 { Some(k) } else { None }
    }
'''
assert old in s, 'value digest anchor not found'
p.write_text(s.replace(old, new))

p = Path('src/conv.rs')
s = p.read_text()
old_import = "use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};\n"
new_import = old_import + "use std::sync::atomic::{AtomicU64, Ordering::Relaxed};\n\nstatic MSI_HINT_TOTAL: AtomicU64 = AtomicU64::new(0);\nstatic MSI_HINT_SAMPLE: AtomicU64 = AtomicU64::new(0);\nstatic MSI_HINT_BOTH: AtomicU64 = AtomicU64::new(0);\nstatic MSI_HINT_EQ: AtomicU64 = AtomicU64::new(0);\nstatic MSI_HINT_EQ_TRUE: AtomicU64 = AtomicU64::new(0);\nstatic MSI_HINT_NEQ: AtomicU64 = AtomicU64::new(0);\nstatic MSI_HINT_NEQ_TRUE: AtomicU64 = AtomicU64::new(0);\n"
assert old_import in s, 'conv import anchor not found'
s = s.replace(old_import, new_import, 1)

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
        let n = MSI_HINT_TOTAL.fetch_add(1, Relaxed) + 1;
        let raw_eq = std::ptr::eq(x, y);
        let sampled = !raw_eq && (n & 63) == 0;
        let mut cached_eq = false;
        let mut cached_neq = false;
        if sampled {
            MSI_HINT_SAMPLE.fetch_add(1, Relaxed);
            if let (Some(dx), Some(dy)) = (x.cached_digest(), y.cached_digest()) {
                MSI_HINT_BOTH.fetch_add(1, Relaxed);
                if dx == dy {
                    MSI_HINT_EQ.fetch_add(1, Relaxed);
                    cached_eq = true;
                } else {
                    MSI_HINT_NEQ.fetch_add(1, Relaxed);
                    cached_neq = true;
                }
            }
        }

        let result = if raw_eq {
            true
        } else {
            let x = self.force_thunk(depth, x);
            let y = self.force_thunk(depth, y);
            if std::ptr::eq(x, y) {
                true
            } else {
                self.unify_general::<RIGID>(depth, x, y)
            }
        };

        if sampled {
            if cached_eq && result { MSI_HINT_EQ_TRUE.fetch_add(1, Relaxed); }
            if cached_neq && result { MSI_HINT_NEQ_TRUE.fetch_add(1, Relaxed); }
        }
        if n == 3_000_000 {
            eprintln!(
                "MSI_CACHED_HINT total={} sample={} both={} eq={} eq_true={} neq={} neq_true={}",
                MSI_HINT_TOTAL.load(Relaxed),
                MSI_HINT_SAMPLE.load(Relaxed),
                MSI_HINT_BOTH.load(Relaxed),
                MSI_HINT_EQ.load(Relaxed),
                MSI_HINT_EQ_TRUE.load(Relaxed),
                MSI_HINT_NEQ.load(Relaxed),
                MSI_HINT_NEQ_TRUE.load(Relaxed),
            );
        }
        result
    }
'''
assert old in s, 'unify anchor not found'
p.write_text(s.replace(old, new))
print('applied MSI cached semantic hint census v22')
