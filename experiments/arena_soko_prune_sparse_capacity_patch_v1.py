#!/usr/bin/env python3
"""Test direct prune memo capacity only AFTER qualifying sparse reset.

The 1024->4096 source-pinned experiment on the original full-array reset
regressed. Sparse touched-slot clearing changes reset cost; this experiment
tests the conditional interaction, not a broader memoization theorem.
"""
from pathlib import Path
import sys

root = Path(sys.argv[1])
power = int(sys.argv[2])
assert power in (12, 14), "Only pinned 4K / 16K sizes are in this experiment"
p = root / "src/checker/cache.rs"
s = p.read_text()
assert "pub(crate) struct PruneMemo<'a>" in s, "Requires qualified sparse parent"
old_len = "pub(crate) const PRUNE_DM_LEN: usize = 1 << 10;"
old_shift = "pub(crate) const PRUNE_DM_SHIFT: u32 = 64 - 10;"
assert s.count(old_len) == s.count(old_shift) == 1, "Memo layout changed"
new_len = f"pub(crate) const PRUNE_DM_LEN: usize = 1 << {power};"
new_shift = f"pub(crate) const PRUNE_DM_SHIFT: u32 = 64 - {power};"
s = s.replace(old_len, new_len).replace(old_shift, new_shift)
assert s.count(new_len) == 1 and s.count(new_shift) == 1
p.write_text(s)
print(f"SPARSE_PRUNE_MEMO_CAPACITY=1024_TO_{1 << power}", flush=True)
