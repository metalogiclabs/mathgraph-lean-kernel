#!/usr/bin/env python3
from pathlib import Path

p=Path("src/conv.rs")
c=p.read_text()

old="""                    if heads_match {
                        return self.unfold_pair(depth, t, t2);
                    }
"""
new="""                    if heads_match {
                        // Flash transfer of the previously verified longge4 selector:
                        // when the two equivalent unfold heads have materially different
                        // spine lengths, try the shorter presentation first. If it makes
                        // semantic progress, recurse immediately and avoid evaluating the
                        // other representation on this step.
                        let sx_len = sx.len();
                        let sy_len = sy.len();
                        let gap = if sx_len >= sy_len { sx_len - sy_len } else { sy_len - sx_len };
                        let longer = sx_len.max(sy_len);
                        if gap >= 2 && longer >= 4 {
                            if sx_len <= sy_len {
                                let v1 = self.unfold_value(depth, t);
                                if !std::ptr::eq(v1, t) {
                                    return self.unify::<true>(depth, v1, t2);
                                }
                                let v2 = self.unfold_value(depth, t2);
                                if !std::ptr::eq(v2, t2) {
                                    return self.unify::<true>(depth, t, v2);
                                }
                            } else {
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
                        return self.unfold_pair(depth, t, t2);
                    }
"""
if c.count(old)!=1:
    raise SystemExit(f"longge4 transfer anchor mismatch: {c.count(old)}")
c=c.replace(old,new,1)
p.write_text(c)
print("QCKN_UNFOLD_LONGGE4_TRANSFER_V1_PATCH=PASS")
