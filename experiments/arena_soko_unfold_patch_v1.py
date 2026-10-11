#!/usr/bin/env python3
"""Single-table unfolding cache initial capacity intervention.

Pins intgrah/sokonanoda@7645b1e. Changes only initial capacity of
unfold_hc in src/checker/cache.rs; the cached relation and proof rules do not
change. Matched 196-case verdicts are necessary, not sufficient, to promote.
"""
import pathlib
import sys

p=pathlib.Path(sys.argv[1]) / "src/checker/cache.rs"
s=p.read_text()
old="#[cap(SESSION)] unfold_hc:"
new="#[cap(SESSION * 4)] unfold_hc:"
assert s.count(old)==1, "pinned cache schema changed"
p.write_text(s.replace(old,new))
assert p.read_text().count(new)==1
print("SOKO_UNFOLD_CAPACITY_PATCH=8192_TO_32768",flush=True)
