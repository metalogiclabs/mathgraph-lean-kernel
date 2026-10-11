#!/usr/bin/env python3
r"""Proof-scoped zero-copy environment representative, source exact.

Given exact source E and relevant support M, a verifier-produced previous
near-only projection N containing M can be used as an evaluation cache
representative *without copying a new frame*, provided M and N have the
same highest binder index, source/lsub identity, and all M values available.

Unlike a general projection, the resulting frame may retain extra slots.
This is justified ONLY for the current expression's protected support M,
never as a global semantic equivalence; the source must use prune_env solely
via key_env(env, expr) with expr.fv_mask(). Every successful bypass replays
the original cold projection in --shadow and checks relevant observations.
No verdict rule or external trust policy is modified.
"""
import sys
from pathlib import Path
assert len(sys.argv) in (2, 3)
shadow=len(sys.argv)==3 and sys.argv[2]=="--shadow"
assert len(sys.argv)==2 or shadow
path=Path(sys.argv[1])/"src/checker/eval/environment.rs"
source=path.read_text()
# Source contract: the only direct pruning consumer is expression keying.
assert source.count("self.prune_env(env, e.as_ref().fv_mask())")==1
assert source.count("self.prune_env(")==1
marker="impl<'t> TypeChecker<'_, 't, '_> {"
assert source.count(marker)==1
source=source.replace(marker,
    "const MG_ZERO_COPY_REP_SHADOW: bool = "+str(shadow).lower()+";\n\n"+marker,1)
start=source.index("    fn prune_env(")
stop=source.index("    #[inline(never)]\n    fn prune_env_cold(",start)
block=source[start:stop]
needle="        match e {\n"
assert block.count(needle)>=2
block=block.replace(needle,
    "        let mut certified_superset: Option<E<'t>> = None;\n"+needle,1)
receipt="""                let (m, r) = prune.get();
                if m == mask
                    && let Some(r) = r
                {
                    return r;
                }"""
assert block.count(receipt)==2
guard=receipt+"""
                // The saved projection is tied to this EXACT source E.
                // The max-index guard below preserves Env::len on reuse.
                if (mask & value::FAR) == 0
                    && (m & value::FAR) == 0
                    && m != mask
                    && (m & mask) == mask
                    && (3..=8).contains(&mask.count_ones())
                    && let Some(saved) = r
                {
                    certified_superset = Some(saved);
                }"""
block=block.replace(receipt,guard)
fallback="        self.prune_env_cold(e, mask, slot)"
assert block.count(fallback)==1
replacement=r"""        if let Some(saved) = certified_superset
            && !std::ptr::eq(saved, e)
            && let value::Env::Framed {
                mask: actual, cut, rest: None, lsub: saved_lsub, ..
            } = saved
            && u32::from(*cut) == value::NEAR
            && (*actual & value::FAR) == 0
            && (*actual & mask) == mask
            && actual.leading_zeros() == mask.leading_zeros()
            && saved_lsub.map(Id::of) == e.lsub().map(Id::of)
        {
            // We return a verifier-created frame as a representative for
            // THIS expression's relevant variables; extra slots are inert.
            // Critically no frame allocation, slot copying or rehashing.
            if MG_ZERO_COPY_REP_SHADOW {
                let cold = self.prune_env_cold(e, mask, slot);
                let same_levels = match (cold.lsub(), saved.lsub()) {
                    (None, None) => true,
                    (Some(a), Some(b)) => std::ptr::eq(a, b),
                    _ => false,
                };
                assert!(same_levels, "MG_ZERO_COPY_LSUB_MISMATCH");
                assert!(cold.len() == saved.len(), "MG_ZERO_COPY_LEN_MISMATCH");
                let mut required = mask;
                while required != 0 {
                    let index = required.trailing_zeros() as u16;
                    let same = match (cold.lookup(index), saved.lookup(index)) {
                        (None, None) => true,
                        (Some(a), Some(b)) => std::ptr::eq(a, b),
                        _ => false,
                    };
                    assert!(same, "MG_ZERO_COPY_RELEVANT_VALUE_MISMATCH");
                    required &= required - 1;
                }
                static FIRST_CHECK: std::sync::atomic::AtomicBool =
                    std::sync::atomic::AtomicBool::new(false);
                if !FIRST_CHECK.swap(true, std::sync::atomic::Ordering::Relaxed) {
                    eprintln!("MG_ZERO_COPY_REP_SHADOW_CHECKED=COLD_RELEVANT_OBSERVATIONS");
                }
            }
            // Preserve original one-entry and sparse direct memo writes.
            self.tc_cache.prune_dm.put(slot, Id::of(e), mask, saved);
            match e {
                value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } => {
                    prune.set((mask, Some(saved)));
                }
                value::Env::Nil { .. } => {}
            }
            return saved;
        }
        self.prune_env_cold(e, mask, slot)"""
block=block.replace(fallback,replacement)
source=source[:start]+block+source[stop:]
assert source.count("MG_ZERO_COPY_REP_SHADOW_CHECKED")==1
assert source.count("self.prune_env_cold(e, mask, slot)")==2
path.write_text(source)
print("MG_ZERO_COPY_REP=EXACT_SOURCE_MAX_INDEX_PRESERVED_SHADOW_"+str(shadow).upper(),flush=True)
