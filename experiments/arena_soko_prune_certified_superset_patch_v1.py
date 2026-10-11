#!/usr/bin/env python3
r"""Narrow source-certified pruning reuse: project a retained superset frame.

For a given exact source environment E and near-only masks M subset N,
pi_M(pi_N(E)) = pi_M(E), provided the previously obtained projection truly
contains every requested value with the original relative binder indexing.
Use only E's own verifier-written one-entry prune receipt, not a new global
cache or cross-source pointer equivalence. Disable when far bits, missing
requested bindings, or a non-canonical frame are present.

--shadow recomputes the independent original cold projection for every
successful shortcut, and compares source lsub, length and all requested values.
It deliberately does not relax the original kernel's logical judgments.
"""
import sys
from pathlib import Path

assert len(sys.argv) in (2, 3)
shadow = len(sys.argv) == 3 and sys.argv[2] == "--shadow"
assert len(sys.argv) == 2 or shadow

path = Path(sys.argv[1]) / "src/checker/eval/environment.rs"
source = path.read_text()
impl_marker = "impl<'t> TypeChecker<'_, 't, '_> {"
assert source.count(impl_marker) == 1
source = source.replace(
    impl_marker,
    "const MG_CERT_SUPERMASK_SHADOW: bool = "
    + str(shadow).lower()
    + ";\n\n" + impl_marker,
    1,
)
begin = source.index("    fn prune_env(")
end = source.index("    #[inline(never)]\n    fn prune_env_cold(", begin)
block = source[begin:end]

# Preserve all original fast paths. The original Cell identifies exactly the
# source whose verifier-produced projection is being reused.
match_marker = "        match e {\n"
assert block.count(match_marker) >= 2
block = block.replace(
    match_marker,
    "        let mut cached_superframe: Option<E<'t>> = None;\n" + match_marker,
    1,
)
receipt = """                let (m, r) = prune.get();
                if m == mask
                    && let Some(r) = r
                {
                    return r;
                }"""
assert block.count(receipt) == 2
capture = receipt + """
                // Near-only, strictly contained requests with >=3 and <=8
                // live slots: avoid adding overhead to cheap one-slot lookups.
                if (mask & value::FAR) == 0
                    && (m & value::FAR) == 0
                    && m != mask
                    && (m & mask) == mask
                    && (3..=8).contains(&mask.count_ones())
                    && let Some(saved) = r
                {
                    cached_superframe = Some(saved);
                }"""
block = block.replace(receipt, capture)
original_fallback = "        self.prune_env_cold(e, mask, slot)"
assert block.count(original_fallback) == 1
candidate = r"""        // An actual cached Framed superset has the same de Bruijn coordinates
        // as its original source. Re-select already verified slots directly,
        // rather than looking them up individually or rewalking Cons parents.
        if let Some(previous) = cached_superframe
            && !std::ptr::eq(previous, e)
            && let value::Env::Framed {
                mask: previous_support, slots, cut, rest: None,
                lsub: previous_lsub, ..
            } = previous
            && u32::from(*cut) == value::NEAR
            && (*previous_support & value::FAR) == 0
            && (*previous_support & mask) == mask
            && previous_lsub.map(Id::of) == e.lsub().map(Id::of)
        {
            let mut selected_ranks = select_ranks(mask, *previous_support);
            let lsub = e.lsub();
            let mut slots_hash = lsub.map_or(0, |l| Id::of(l).addr() as u64);
            let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] =
                [const { std::mem::MaybeUninit::uninit() }; 64];
            let mut n = 0usize;
            while selected_ranks != 0 {
                let rank = selected_ranks.trailing_zeros() as usize;
                selected_ranks &= selected_ranks - 1;
                let v = slots[rank];
                buf[n].write(v);
                slots_hash = slots_hash.wrapping_mul(GOLDEN)
                    .wrapping_add(Id::of(v).addr() as u64);
                n += 1;
            }
            let selected: &[V<'t>] = unsafe {
                std::slice::from_raw_parts(buf.as_ptr().cast::<V<'t>>(), n)
            };
            let fast = self.intern_frame(
                slots_hash, mask, selected, value::NEAR, None, lsub
            );

            if MG_CERT_SUPERMASK_SHADOW {
                // Independent original algorithm is the safety authority.
                // It is replayed for EACH successful fast-path invocation.
                let original = self.prune_env_cold(e, mask, slot);
                let same_levels = match (original.lsub(), fast.lsub()) {
                    (None, None) => true,
                    (Some(a), Some(b)) => std::ptr::eq(a, b),
                    _ => false,
                };
                assert!(same_levels, "MG_SUPERMASK_LSUB_MISMATCH");
                assert!(original.len() == fast.len(), "MG_SUPERMASK_LEN_MISMATCH");
                let mut live = mask;
                while live != 0 {
                    let index = live.trailing_zeros() as u16;
                    let equal = match (original.lookup(index), fast.lookup(index)) {
                        (None, None) => true,
                        (Some(a), Some(b)) => std::ptr::eq(a, b),
                        _ => false,
                    };
                    assert!(equal, "MG_SUPERMASK_VALUE_MISMATCH");
                    live &= live - 1;
                }
                static FIRST_CHECK: std::sync::atomic::AtomicBool =
                    std::sync::atomic::AtomicBool::new(false);
                if !FIRST_CHECK.swap(
                    true, std::sync::atomic::Ordering::Relaxed
                ) {
                    eprintln!("MG_CERT_SUPERMASK_SHADOW_CHECKED=ORIGINAL_COLD");
                }
            }
            // Keep the original source's exact cache semantics and eviction.
            self.tc_cache.prune_dm.put(slot, Id::of(e), mask, fast);
            match e {
                value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } => {
                    prune.set((mask, Some(fast)));
                }
                value::Env::Nil { .. } => {}
            }
            return fast;
        }
        self.prune_env_cold(e, mask, slot)"""
block=block.replace(original_fallback,candidate)
source=source[:begin]+block+source[end:]
assert source.count("MG_SUPERMASK_VALUE_MISMATCH")==1
assert source.count("MG_CERT_SUPERMASK_SHADOW_CHECKED=")==1
assert source.count("self.prune_env_cold(e, mask, slot)")==2
path.write_text(source)
print(
    "MG_CERT_SUPERMASK_PATCH=NEAR_ONLY_TYPED_RECEIPT_DIRECT_FRAME_SHADOW_"
    + str(shadow).upper(), flush=True
)
