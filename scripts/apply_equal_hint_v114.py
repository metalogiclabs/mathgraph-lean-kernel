#!/usr/bin/env python3
from pathlib import Path

p=Path("src/conv.rs")
c=p.read_text()

old="""                    } else {
                        self.unfold_pair(depth, t, t2)
                    }
"""
new="""                    } else {
                        let lx = sx.len();
                        let ly = sy.len();
                        let a = lx.min(ly);
                        let b = lx.max(ly);
                        if a == 1 && (b == 3 || b == 4 || b == 6) {
                            if lx < ly {
                                let v1 = self.unfold_value(depth, t);
                                if !std::ptr::eq(v1, t) {
                                    return self.unify::<true>(depth, v1, t2);
                                }
                                let v2 = self.unfold_value(depth, t2);
                                if !std::ptr::eq(v2, t2) {
                                    return self.unify::<true>(depth, t, v2);
                                }
                            } else if ly < lx {
                                let v2 = self.unfold_value(depth, t2);
                                if !std::ptr::eq(v2, t2) {
                                    return self.unify::<true>(depth, t, v2);
                                }
                                let v1 = self.unfold_value(depth, t);
                                if !std::ptr::eq(v1, t) {
                                    return self.unify::<true>(depth, v1, t2);
                                }
                            }
                        }
                        self.unfold_pair(depth, t, t2)
                    }
"""
n=c.count(old)
if n!=1:
    raise SystemExit(f"V114 anchor expected 1, found {n}")
p.write_text(c.replace(old,new,1))
print("APPLY_V114_EQUAL_HINT=PASS")
