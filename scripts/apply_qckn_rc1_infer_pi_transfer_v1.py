#!/usr/bin/env python3
from pathlib import Path

# flash.rs: add one explicit promoted capability switch
p=Path("src/flash.rs")
c=p.read_text()
anchor="""pub(crate) const ORDINARY_UNFOLD_NEUTRAL: bool = false;
"""
insert=anchor+"""pub(crate) const INFER_PI_DEMAND_BYPASS: bool = true;
"""
if c.count(anchor)!=1:
    raise SystemExit(f"flash anchor mismatch: {c.count(anchor)}")
c=c.replace(anchor,insert,1)
p.write_text(c)

# infer.rs: preserve original semantics; only avoid force_all when already Pi
p=Path("src/infer.rs")
c=p.read_text()
old="""        while let Some(arg) = args.pop() {
            let fty_f = self.force_all(depth, fty);
            let (domain, body) = match fty_f {
"""
new="""        while let Some(arg) = args.pop() {
            let fty_f = if crate::flash::INFER_PI_DEMAND_BYPASS {
                match fty {
                    Value::Pi { .. } => fty,
                    _ => self.force_all(depth, fty),
                }
            } else {
                self.force_all(depth, fty)
            };
            let (domain, body) = match fty_f {
"""
if c.count(old)!=1:
    raise SystemExit(f"infer_app anchor mismatch: {c.count(old)}")
c=c.replace(old,new,1)
p.write_text(c)

print("QCKN_RC1_INFER_PI_TRANSFER_V1_PATCH=PASS")
