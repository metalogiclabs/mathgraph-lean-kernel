#!/usr/bin/env python3
"""Test the exact-size collision hypothesis for prune_env direct-mapped cache.

Only changes cache slot count and matching shift, preserving all semantic
check rules, hashes and collision validation under pinned Soko.
"""
import pathlib
import sys

p=pathlib.Path(sys.argv[1])/"src/checker/cache.rs"
s=p.read_text()
a="pub(crate) const PRUNE_DM_LEN: usize = 1 << 10;"
b="pub(crate) const PRUNE_DM_LEN: usize = 1 << 12;"
c="pub(crate) const PRUNE_DM_SHIFT: u32 = 64 - 10;"
d="pub(crate) const PRUNE_DM_SHIFT: u32 = 64 - 12;"
assert s.count(a)==1 and s.count(c)==1,"pinned original memo source changed"
s=s.replace(a,b).replace(c,d)
p.write_text(s)
assert p.read_text().count(b)==1 and p.read_text().count(d)==1
print("SOKO_PRUNE_MEMO_PATCH=1024_TO_4096",flush=True)
