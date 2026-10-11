#!/usr/bin/env python3
"""Only enlarge the exact direct-mapped pruning memo, keeping hash shift in sync.
Used as standalone and after the independently source-checked sparse reset.
"""
from pathlib import Path
import sys

p=Path(sys.argv[1])/"src/checker/cache.rs"
s=p.read_text()
old_len="pub(crate) const PRUNE_DM_LEN: usize = 1 << 10;"
old_shift="pub(crate) const PRUNE_DM_SHIFT: u32 = 64 - 10;"
assert s.count(old_len)==1 and s.count(old_shift)==1,"Pinned source contract changed"
s=s.replace(old_len,"pub(crate) const PRUNE_DM_LEN: usize = 1 << 12;")
s=s.replace(old_shift,"pub(crate) const PRUNE_DM_SHIFT: u32 = 64 - 12;")
p.write_text(s)
print("PRUNE_WIDE_PATCH=1024_TO_4096_WITH_EXACT_HASH_SHIFT",flush=True)
