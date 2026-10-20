#!/usr/bin/env python3
"""Propagate an already verified parent's syntactic variable support into App inference.

For App(f,a), support(f) and support(a) are subsets of support(App(f,a))
at the SAME binder depth. Source key_env(env,e) is already needed by the
type cache, and retains exact universe substitution. Descend on that
environment instead of the pre-projection source environment.
This retains all proof/type/axiom validation; no memo is assumed valid
under any environment outside the source-authored projection.
"""
import pathlib,sys
p=pathlib.Path(sys.argv[1])/"src/checker/infer.rs"
s=p.read_text()
source1="        let key = (Id::of(self.key_env(env, e)), e);"
target1="""        // Reuse the source-authorized relevant environment for immediate
        // application children. The type cache already computes this.
        let relevant_env = self.key_env(env, e);
        let key = (Id::of(relevant_env), e);"""
source2="            App { .. } => self.infer_app_v(flag, depth, env, ctx, e),"
target2="            App { .. } => self.infer_app_v(flag, depth, relevant_env, ctx, e),"
assert s.count(source1)==1,"source drift: inferred cache key"
assert s.count(source2)==1,"source drift: application inference"
s=s.replace(source1,target1).replace(source2,target2)
p.write_text(s)
print("FLASH_APP_SUPPORT_TRANSPORT=APPLIED_SOURCE_SCOPED",flush=True)
