#!/usr/bin/env python3
from pathlib import Path

p=Path("src/conv.rs")
c=p.read_text()

old="""        let cacheable = is_cacheable(x) || is_cacheable(y);
"""
new="""        let closed_rigid_pair =
            matches!(x, Value::Rigid { .. })
                && matches!(y, Value::Rigid { .. })
                && x.is_closed()
                && y.is_closed();
        let cacheable = is_cacheable(x) || is_cacheable(y) || closed_rigid_pair;
"""
if c.count(old) != 1:
    raise SystemExit(f"cacheable anchor mismatch: {c.count(old)}")
c=c.replace(old,new,1)
p.write_text(c)
print("QCKN_CLOSED_RIGID_CONV_CACHE_V1_PATCH=PASS")
