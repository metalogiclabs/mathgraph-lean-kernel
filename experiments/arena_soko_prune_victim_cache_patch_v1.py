#!/usr/bin/env python3
"""Bounded, source-exact second-chance cache for displaced semantic projections.

The pinned checker already stores a single mask and result in each source
environment and a direct-mapped (source,mask,result) PruneMemo. When the
single-source mask is different and the direct map has lost an old result,
a bounded second-chance table can recover it without repeating the full
environment traversal. Every recovered value is an original verifier-made
value identified by BOTH exact source Env identity and exact support mask.
Cache reset clears ALL references before its arena is recycled.

This is an isolated performance hypothesis; NO acceptance or rank claim.
"""
from pathlib import Path
import sys

root=Path(sys.argv[1])
cache=root/"src/checker/cache.rs"
env=root/"src/checker/eval/environment.rs"
s=cache.read_text()
assert s.count("pub(crate) const PRUNE_DM_SHIFT: u32 = 64 - 10;")==1
s=s.replace("pub(crate) const PRUNE_DM_SHIFT: u32 = 64 - 10;",
"""pub(crate) const PRUNE_DM_SHIFT: u32 = 64 - 10;
const PRUNE_VICTIM_LEN: usize = 1 << 15;
const PRUNE_VICTIM_SHIFT: u32 = 64 - 15;""")
old=r"""pub(crate) struct PruneMemo<'a> {
    slots: Box<[PruneEntry<'a>; PRUNE_DM_LEN]>,
    touched: Vec<usize>,
}

impl<'a> PruneMemo<'a> {
    #[inline]
    pub(crate) fn at(&self, slot: usize) -> PruneEntry<'a> {
        self.slots[slot]
    }

    #[inline]
    pub(crate) fn put(&mut self, slot: usize, source: Id<'a, Env<'a>>, mask: u64, result: E<'a>) {
        if self.slots[slot].0.is_none() {
            self.touched.push(slot);
        }
        self.slots[slot] = (Some(source), mask, Some(result));
    }
}

impl Reset for PruneMemo<'_> {
    fn with_cap(_: usize) -> Self {
        Self {
            slots: Box::new([(None, 0, None); PRUNE_DM_LEN]),
            touched: Vec::new(),
        }
    }

    fn reset(&mut self) {
        for slot in self.touched.drain(..) {
            self.slots[slot] = (None, 0, None);
        }
    }

    fn reset_shrink(&mut self) {
        self.reset();
    }
}"""
new=r"""pub(crate) struct PruneMemo<'a> {
    // Original high-probability first-level lookup, unchanged.
    slots: Box<[PruneEntry<'a>; PRUNE_DM_LEN]>,
    touched: Vec<usize>,
    // Fixed bounded exact secondary table; no inserted non-verifier values.
    victim: Box<[PruneEntry<'a>]>,
    victim_touched: Vec<usize>,
}

impl<'a> PruneMemo<'a> {
    #[inline(always)]
    fn victim_slot(source: Id<'a, Env<'a>>, mask: u64) -> usize {
        let hash = (source.addr() as u64).wrapping_mul(GOLDEN)
            ^ mask.wrapping_mul(0xD6E8_FEB8_6659_FD93);
        (hash >> PRUNE_VICTIM_SHIFT) as usize
    }

    #[inline]
    pub(crate) fn at(&self, slot: usize) -> PruneEntry<'a> {
        self.slots[slot]
    }

    #[inline]
    pub(crate) fn displaced(&self, source: Id<'a, Env<'a>>, mask: u64) -> Option<E<'a>> {
        let (_, _, _) = (source, mask, PRUNE_VICTIM_LEN);
        let (from, m, result) = self.victim[Self::victim_slot(source, mask)];
        if from == Some(source) && m == mask {
            result
        } else {
            None
        }
    }

    #[inline]
    pub(crate) fn put(&mut self, slot: usize, source: Id<'a, Env<'a>>, mask: u64, result: E<'a>) {
        let previous = self.slots[slot];
        if let (Some(old_source), old_mask, Some(old_result)) = previous {
            if old_source != source || old_mask != mask {
                let vi = Self::victim_slot(old_source, old_mask);
                if self.victim[vi].0.is_none() {
                    self.victim_touched.push(vi);
                }
                self.victim[vi] = (Some(old_source), old_mask, Some(old_result));
            }
        } else {
            self.touched.push(slot);
        }
        self.slots[slot] = (Some(source), mask, Some(result));
    }
}

impl Reset for PruneMemo<'_> {
    fn with_cap(_: usize) -> Self {
        Self {
            slots: Box::new([(None, 0, None); PRUNE_DM_LEN]),
            touched: Vec::new(),
            victim: vec![(None, 0, None); PRUNE_VICTIM_LEN].into_boxed_slice(),
            victim_touched: Vec::new(),
        }
    }

    fn reset(&mut self) {
        for slot in self.touched.drain(..) {
            self.slots[slot] = (None, 0, None);
        }
        for slot in self.victim_touched.drain(..) {
            self.victim[slot] = (None, 0, None);
        }
    }

    fn reset_shrink(&mut self) {
        self.reset();
    }
}"""
assert s.count(old)==1,"Expected exact qualified sparse PruneMemo source not found"
s=s.replace(old,new)
cache.write_text(s)

s=env.read_text()
start=s.index("    fn prune_env(")
end=s.index("    #[inline(never)]\n    fn prune_env_cold(",start)
a=s[start:end]
assert a.count("        match e {")==2
assert a.count("                let (m, r) = prune.get();")==2
assert a.count("        self.prune_env_cold(e, mask, slot)")==1
# Read old source-cell cache without changing the proven primary hit paths.
head="""        match e {
            value::Env::Nil { .. } => return e,"""
assert a.count(head)==1
a=a.replace(head,"""        let mut old_cell_displaced = false;
        match e {
            value::Env::Nil { .. } => return e,""")
a=a.replace("                let (m, r) = prune.get();",
"""                let (m, r) = prune.get();
                old_cell_displaced |= r.is_some() && m != mask;""")
# Preserve memo hit and its canonical result. Only exact displaced keys
# are eligible; else fall through to the whole original cold checker path.
old="""        self.prune_env_cold(e, mask, slot)"""
new="""        // This is a second-chance hit ONLY if a different same-source
        // support mask had displaced the original per-env memo. Never
        // use a result from any different source, even with a matching hash.
        if old_cell_displaced
            && let Some(hit) = self.tc_cache.prune_dm.displaced(Id::of(e), mask)
        {
            match e {
                value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } => {
                    prune.set((mask, Some(hit)));
                }
                value::Env::Nil { .. } => {}
            }
            return hit;
        }
        self.prune_env_cold(e, mask, slot)"""
assert a.count(old)==1
a=a.replace(old,new)
s=s[:start]+a+s[end:]
env.write_text(s)
print("PRUNE_BOUNDED_VICTIM_CACHE=APPLIED_EXACT_KEYS_FAIL_CLOSED",flush=True)
