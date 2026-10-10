#!/usr/bin/env python3
"""Apply one isolated, syntax-checked fast path to exact pinned sokonanoda.

An identical immutable interned value is definitionally equal to itself;
skip proof-irrelevance search and type-directed conversion. Not a new axiom.
"""
import pathlib
import sys

p=pathlib.Path(sys.argv[1]) / "src/checker/conv.rs"
s=p.read_text()
a="""    pub(crate) fn def_eq_at(&mut self, depth: u32, vx: V<'t>, vy: V<'t>) -> bool {
        self.unbudgeted(|s| s.try_proof_irrel_at(depth, vx, vy) || s.unify::<true>(depth, vx, vy))
    }
"""
b="""    #[inline]
    pub(crate) fn def_eq_at(&mut self, depth: u32, vx: V<'t>, vy: V<'t>) -> bool {
        std::ptr::eq(vx, vy)
            || self.unbudgeted(|s| s.try_proof_irrel_at(depth, vx, vy) || s.unify::<true>(depth, vx, vy))
    }
"""
assert s.count(a)==1, "pinned upstream source must match the declared fast-path proof obligation"
p.write_text(s.replace(a,b))
print("SOKO_EXACT_DEF_EQ_FASTPATH=APPLIED")
