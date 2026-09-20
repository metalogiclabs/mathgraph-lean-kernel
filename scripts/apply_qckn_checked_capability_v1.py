#!/usr/bin/env python3
from pathlib import Path

p=Path("src/infer.rs")
c=p.read_text()

old="""    fn uparam_scope(&self) -> CheckScope<'t> {
        match self.declar_info {
            Some(info) => CheckScope::Under(info.uparams),
            None => CheckScope::NoUparams,
        }
    }
"""
new="""    fn uparam_scope(&self) -> CheckScope<'t> {
        match self.declar_info {
            Some(info) if self.ctx.read_levels(info.uparams).is_empty() => CheckScope::NoUparams,
            Some(info) => CheckScope::Under(info.uparams),
            None => CheckScope::NoUparams,
        }
    }
"""
if c.count(old) != 1:
    raise SystemExit(f"uparam_scope anchor mismatch: {c.count(old)}")
c=c.replace(old,new,1)
p.write_text(c)
print("QCKN_CHECKED_CAPABILITY_V1_PATCH=PASS")
