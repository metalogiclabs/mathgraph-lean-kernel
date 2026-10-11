#!/usr/bin/env python3
"""Controlled 2x -> 4x PtrMap growth test, preserving hash-index shift invariant."""
import pathlib,sys
p=pathlib.Path(sys.argv[1])/"src/checker/ptrmap.rs"
s=p.read_text()
a="let n = self.tags.len() * 2;"
b="let n = self.tags.len() * 4;"
c="self.shift -= 1;"
d="self.shift -= 2;"
assert s.count(a)==1 and s.count(c)==1,"pinned growth implementation diverged"
s=s.replace(a,b).replace(c,d)
p.write_text(s)
print("SOKO_GROWTH_FACTOR_PATCH=2x_TO_4x_WITH_EXACT_SHIFT",flush=True)
