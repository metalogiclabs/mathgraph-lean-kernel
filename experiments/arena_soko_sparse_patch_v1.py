#!/usr/bin/env python3
"""Replace full-table resets with exact touched-slot clearing for prune memo.

This is source-pinned performance-only work. No conversion/type rules change.
Touched indices enumerate every written slot once until each session reset;
the reset clears all old references before the memory arena is recycled.
"""
from pathlib import Path
import sys
root=Path(sys.argv[1])
cache=root/"src/checker/cache.rs"
env=root/"src/checker/eval/environment.rs"
s=cache.read_text()
anchor="macro_rules! caches {"
new='''type PruneEntry<'a> = (Option<Id<'a, Env<'a>>>, u64, Option<E<'a>>);

pub(crate) struct PruneMemo<'a> {
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
}

'''
assert s.count(anchor)==1
s=s.replace(anchor,new+anchor)
old="#[cap(0)] prune_dm: Box<[(Option<Id<'a, Env<'a>>>, u64, Option<E<'a>>); PRUNE_DM_LEN]>,"
assert s.count(old)==1
s=s.replace(old,"#[cap(0)] prune_dm: PruneMemo<'a>,")
cache.write_text(s)
q=env.read_text()
old_get="let ent = self.tc_cache.prune_dm[slot];"
assert q.count(old_get)==1
q=q.replace(old_get,"let ent = self.tc_cache.prune_dm.at(slot);")
old_put="self.tc_cache.prune_dm[slot] = (Some(Id::of(e)), mask, Some(r));"
assert q.count(old_put)==1
q=q.replace(old_put,"self.tc_cache.prune_dm.put(slot, Id::of(e), mask, r);")
env.write_text(q)
print("SPARSE_PRUNE_RESET_PATCH=APPLIED_WITH_EXACT_TOUCHED_CLEAR",flush=True)
