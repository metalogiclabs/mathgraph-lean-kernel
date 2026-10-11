#!/usr/bin/env python3
"""Exact large-table-only 4x growth; preserve PtrMap hash-index invariant."""
import pathlib,sys
p=pathlib.Path(sys.argv[1])/"src/checker/ptrmap.rs"
s=p.read_text()
a="let n = self.tags.len() * 2;"
b="let four = self.tags.len() >= (1 << 14);\n        let n = self.tags.len() * if four { 4 } else { 2 };"
c="self.shift -= 1;"
d="self.shift -= if four { 2 } else { 1 };"
assert s.count(a)==1 and s.count(c)==1,"upstream source changed"
p.write_text(s.replace(a,b).replace(c,d))
print("SELECTIVE_GROWTH=2x_SMALL_4x_LARGE_CUTOFF_16384",flush=True)
