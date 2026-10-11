#!/usr/bin/env python3
"""Semantics-preserving single-vacancy insertion for four atomic value caches.

On the pinned Soko source, mk_bvar_hc, mk_sort_hc, mk_natlit_hc and mk_strlit_hc
use memo!(PtrMap), whose miss path probes once, constructs a value, then probes
again in insert().  Those four constructors do not recursively insert into
their same table during the value construction. hashcons! preserves EXACT
lookup / key / canonical output and uses find()'s vacant slot exactly once.
Do NOT globally rewrite memo!: arbitrary computations can mutate same map.
"""
from pathlib import Path
import sys
p=Path(sys.argv[1])/"src/checker/eval/environment.rs"
s=p.read_text()
a=s.index("    pub(crate) fn mk_bvar_hc(")
b=s.index("    pub(crate) fn mk_head_hc(",a)
segment=s[a:b]
assert segment.count("memo!(")==4, "Expected exactly four constructor-only memo calls"
assert segment.count("hashcons!(")==0, "Pinned source changed"
assert "value::mk_bvar_with_empty" in segment
assert "value::mk_sort(self.arena, level)" in segment
assert "value::mk_natlit(self.arena, ptr)" in segment
assert "value::mk_strlit(self.arena, ptr)" in segment
s=s[:a]+segment.replace("memo!(","hashcons!(")+s[b:]
p.write_text(s)
print("ATOMIC_SINGLE_PROBE=4_PURE_VALUE_CONSTRUCTORS",flush=True)
