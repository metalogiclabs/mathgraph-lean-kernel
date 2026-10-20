#!/usr/bin/env python3
"""App-support transport atop either pristine or already source-fused inference.

In source-fused inference the source-level expression context projection has
already been bound to relevant_env; in pristine inference bind it once.
App children have syntactic support included in the parent at the same binder
depth; the original source carries the *same* universe substitution.
Do not relax validation, identity conditions or checking authority.
"""
from pathlib import Path
import sys
if len(sys.argv)!=3:raise SystemExit("usage: SCRIPT ROOT support|compound")
root=Path(sys.argv[1]); mode=sys.argv[2]
assert mode in ("support","compound")
p=root/"src/checker/infer.rs"
s=p.read_text()
needle="        let key = (Id::of(self.key_env(env, e)), e);"
replacement="""        // This is the existing semantic support projection used for type cache.
        let relevant_env = self.key_env(env, e);
        let key = (Id::of(relevant_env), e);"""
if mode=="support":
    assert s.count(needle)==1, "expected pristine source-keyed cache input"
    s=s.replace(needle,replacement)
else:
    assert needle not in s, "expected fused source without pristine cache key"
    assert s.count("        let relevant_env = self.key_env(env, e);")==1
    assert s.count("        let key = (Id::of(relevant_env), e);")==1
old="            App { .. } => self.infer_app_v(flag, depth, env, ctx, e),"
new="            App { .. } => self.infer_app_v(flag, depth, relevant_env, ctx, e),"
assert s.count(old)==1
s=s.replace(old,new)
p.write_text(s)
print("FLASH_COMPOUND_SUPPORT="+mode,flush=True)
