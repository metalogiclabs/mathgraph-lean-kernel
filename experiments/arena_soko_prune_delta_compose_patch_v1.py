#!/usr/bin/env python3
"""Source-locked, proof-preserving incremental semantic pruning from verified overlap.

For original environment E, previous support N and requested support M,
project_M(E) = merge(project_(M∩N)(project_N(E)), project_(M\N)(E))
when both masks are near-only and all requested variables have their original
de Bruijn indices. This script qualifies a deliberately narrow 2+ overlap /
exactly one missing-variable construction. It never invents a bound value.

--shadow independently replays the original prune_env_cold for EVERY successful
shortcut, verifying source lsub and every requested binding by pointer identity.
The performance binary has shadow disabled at compilation time.
"""
from pathlib import Path
import sys
assert len(sys.argv) in (2,3)
shadow = len(sys.argv)==3 and sys.argv[2]=="--shadow"
assert len(sys.argv)==2 or shadow
p=Path(sys.argv[1])/"src/checker/eval/environment.rs"
s=p.read_text()
marker="impl<'t> TypeChecker<'_, 't, '_> {"
assert s.count(marker)==1
s=s.replace(marker,
    "const MG_DELTA_PROJECTION_SHADOW: bool = "+str(shadow).lower()+";\n\n"+marker)
a=s.index("    fn prune_env(")
b=s.index("    #[inline(never)]\n    fn prune_env_cold(",a)
block=s[a:b]

# Read only the source's existing last verified projection. This cell's
# exact-mask fast hit, original 1024-entry memo hit, and Frame cover remain
# ahead of the new path and retain their original proof authority.
needle="""        match e {
            value::Env::Nil { .. } => return e,"""
assert block.count(needle)==1
block=block.replace(needle,
"""        let mut previous: Option<(u64, E<'t>)> = None;
        match e {
            value::Env::Nil { .. } => return e,""")
needle="""                let (m, r) = prune.get();
                if m == mask
                    && let Some(r) = r
                {
                    return r;
                }"""
assert block.count(needle)==2
block=block.replace(needle,"""                let (m, r) = prune.get();
                if m == mask
                    && let Some(r) = r
                {
                    return r;
                }
                previous = r.map(|value| (m, value));""")

needle="""        self.prune_env_cold(e, mask, slot)"""
assert block.count(needle)==1
intervention=r"""        // Source identity and mask support are the complete warrant.
        // Preserve all original fast cache hits above. This path is cold
        // and applies only when most requested bindings are already present
        // in a cached, verifier-created projection and exactly one is new.
        if let Some((old_mask, old_proj)) = previous {
            let overlap = mask & old_mask & !value::FAR;
            let missing = mask & !old_mask & !value::FAR;
            if (mask & value::FAR) == 0
                && (old_mask & value::FAR) == 0
                && overlap.count_ones() >= 2
                && missing.count_ones() == 1
                && mask.count_ones() <= 5
                && !std::ptr::eq(old_proj, e)
            {
                let lsub = e.lsub();
                let mut slots_hash = lsub.map_or(0, |l| Id::of(l).addr() as u64);
                let mut buf = [const { std::mem::MaybeUninit::<V<'t>>::uninit() }; 64];
                let mut n = 0usize;
                let mut out_mask = 0u64;
                let mut rem = mask;
                while rem != 0 {
                    let i = rem.trailing_zeros() as u16;
                    let bit = 1u64 << i;
                    let slot_val = if (overlap & bit) != 0 {
                        old_proj.lookup(i)
                    } else {
                        e.lookup(i)
                    };
                    if let Some(v) = slot_val {
                        buf[n].write(v);
                        slots_hash = slots_hash
                            .wrapping_mul(GOLDEN)
                            .wrapping_add(Id::of(v).addr() as u64);
                        n += 1;
                        out_mask |= bit;
                    }
                    rem &= rem - 1;
                }
                let selected: &[V<'t>] = unsafe {
                    std::slice::from_raw_parts(buf.as_ptr().cast::<V<'t>>(), n)
                };
                let candidate = self.intern_frame(
                    slots_hash, out_mask, selected, value::NEAR, None, lsub
                );

                if MG_DELTA_PROJECTION_SHADOW {
                    // Independent old algorithm, NEVER skipped in shadow.
                    // It deliberately uses the original source environment
                    // rather than the cached value just read.
                    let reference = self.prune_env_cold(e, mask, slot);
                    let same_universes = match (reference.lsub(), candidate.lsub()) {
                        (None, None) => true,
                        (Some(a), Some(b)) => std::ptr::eq(a, b),
                        _ => false,
                    };
                    assert!(same_universes, "MG_DELTA_SHADOW_LSUB_MISMATCH");
                    let mut live = mask;
                    while live != 0 {
                        let index = live.trailing_zeros() as u16;
                        let equal_value = match (
                            reference.lookup(index), candidate.lookup(index)
                        ) {
                            (None, None) => true,
                            (Some(x), Some(y)) => std::ptr::eq(x, y),
                            _ => false,
                        };
                        assert!(equal_value, "MG_DELTA_SHADOW_VALUE_MISMATCH");
                        live &= live - 1;
                    }
                    static FIRST_SHADOW: std::sync::atomic::AtomicBool =
                        std::sync::atomic::AtomicBool::new(false);
                    if !FIRST_SHADOW.swap(true, std::sync::atomic::Ordering::Relaxed) {
                        eprintln!("MG_DELTA_SHADOW_CHECKED=INDEPENDENT_ORIGINAL_COLD");
                    }
                }

                // Exact memo receipt, same as original cold path.
                self.tc_cache.prune_dm.put(slot, Id::of(e), mask, candidate);
                match e {
                    value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } => {
                        prune.set((mask, Some(candidate)));
                    }
                    value::Env::Nil { .. } => {}
                }
                return candidate;
            }
        }
        self.prune_env_cold(e, mask, slot)"""
block=block.replace(needle,intervention)
s=s[:a]+block+s[b:]
assert s.count("MG_DELTA_SHADOW_LSUB_MISMATCH")==1
assert s.count("self.prune_env_cold(e, mask, slot)")==2 # one shadow + one original fallback
p.write_text(s)
print("PRUNE_DELTA_REUSE=SOURCE_EXACT_SINGLE_NEW_VARIABLE_WITH_SHADOW_"+str(shadow).upper(),flush=True)
