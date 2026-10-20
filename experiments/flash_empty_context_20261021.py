#!/usr/bin/env python3
"""Experimental semantic-preserving normalization: the empty consequential environment.

When a source-derived prune carries no surviving slots and no remaining tail,
the result has no term bindings. Canonicalize to the existing lsub-specific
empty environment, preserving universe substitution and source authority.

No theorem, name or proof special case. Compare against unchanged source and
original full-portable tests before any performance claim.
"""
import pathlib,sys
p=pathlib.Path(sys.argv[1])/"src/checker/eval/environment.rs"
s=p.read_text()
old='''        let r = self.intern_frame(slots_hash, out_mask, slots, value::NEAR, rest, lsub);
        self.tc_cache.prune_dm[slot] = (Some(Id::of(e)), mask, Some(r));'''
new='''        // Empty consequential projection: every requested local was absent
        // from the captured frame and there is no far tail. The existing
        // universe-substitution base is the complete semantic environment.
        let r = if out_mask == 0 && rest.is_none() {
            self.lsub_base(lsub)
        } else {
            self.intern_frame(slots_hash, out_mask, slots, value::NEAR, rest, lsub)
        };
        self.tc_cache.prune_dm[slot] = (Some(Id::of(e)), mask, Some(r));'''
assert s.count(old)==1, "SOURCE_DRIFT: expected original memo publication exactly once"
s=s.replace(old,new)
p.write_text(s)
print("FLASH_EMPTY_CONTEXT_NORMALIZATION=APPLIED",flush=True)
