#!/usr/bin/env python3
"""Controlled 16 MiB -> 64 MiB session cache budget test; not a proof rule."""
import pathlib
import sys

p=pathlib.Path(sys.argv[1]) / "src/checker/tc.rs"
s=p.read_text()
old="const SESSION_BUDGET: usize = 16 * 1024 * 1024;"
new="const SESSION_BUDGET: usize = 64 * 1024 * 1024;"
assert s.count(old)==1, "upstream source diverged from pinned causal patch"
p.write_text(s.replace(old,new))
assert p.read_text().count(new)==1
print("SOKO_SESSION_BUDGET_PATCH=16MiB_TO_64MiB",flush=True)
