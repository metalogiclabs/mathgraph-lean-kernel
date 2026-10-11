#!/usr/bin/env python3
"""Source-exact one-live-local semantic pruning: identical Env::Framed value.

When the requested near fv_mask is exactly ONE bit and has no FAR bit,
the only retained local is env.lookup(trailing_zeros(mask)). Both the old
general traversal and the direct lookup return the same value under the
same source environment. If the local is missing, fall through unchanged
to the source algorithm. The resulting frame carries the exact source
mask, a single copied slot, identical lsub hash/rest and cache receipt.
No binder type, universe level, proof or rejection rule may be skipped.
"""
from pathlib import Path
import sys
p=Path(sys.argv[1])/"src/checker/eval/environment.rs"
s=p.read_text()
anchor="""        let lsub = e.lsub();
        let mut slots_hash = lsub.map_or(0, |l| Id::of(l).addr() as u64);"""
assert s.count(anchor)==1,"Exact source cold prune body changed"
assert "self.tc_cache.prune_dm.put(slot, Id::of(e), mask, r);" in s
assert "pub fn lookup(&self, idx: u16)" not in s  # signature belongs to value.rs
injected="""        let lsub = e.lsub();
        // Exact one-local support: reusing a single available slot produces
        // the same sparse near frame as the fully general traversal. Never
        // apply to FAR-dependent, empty or absent-local environments.
        if (mask & value::FAR) == 0 && mask.is_power_of_two() {
            let idx = mask.trailing_zeros() as u16; // 0..=62 by the guard
            if let Some(v) = e.lookup(idx) {
                let initial_hash = lsub.map_or(0, |l| Id::of(l).addr() as u64);
                let slots_hash = initial_hash
                    .wrapping_mul(GOLDEN)
                    .wrapping_add(Id::of(v).addr() as u64);
                let only_slot = [v];
                let r = self.intern_frame(
                    slots_hash, mask, &only_slot, value::NEAR, None, lsub,
                );
                self.tc_cache.prune_dm.put(slot, Id::of(e), mask, r);
                match e {
                    value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } => {
                        prune.set((mask, Some(r)));
                    }
                    value::Env::Nil { .. } => {}
                }
                return r;
            }
        }
        let mut slots_hash = lsub.map_or(0, |l| Id::of(l).addr() as u64);"""
s=s.replace(anchor,injected)
assert s.count("if (mask & value::FAR) == 0 && mask.is_power_of_two()")==1
p.write_text(s)
print("PRUNE_ONEHOT_EXACT_SOURCE_FRAME=APPLIED_WITH_MISSING_FALLBACK",flush=True)
