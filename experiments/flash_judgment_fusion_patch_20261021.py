#!/usr/bin/env python3
"""Source-scoped single-projection fusion experiment (not a proof rule change).

Source: sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d, after
qualified sparse touched-slot prune reset and PtrMap 4x growth.

Reuses EXACTLY the source-authored, same-expression keyed environment rather
than invoking an equivalent source-context projection for a second time.
No new cache, type coercion, proof irrelevance, or relaxed verifier obligations.

Experimental arms: infer, eval, both. The base arm is unmodified.
"""
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: flash_judgment_fusion_patch.py ROOT infer|eval|both")
root = Path(sys.argv[1])
arm = sys.argv[2]
assert arm in ("infer", "eval", "both")

if arm in ("infer", "both"):
    p=root/"src/checker/infer.rs"
    s=p.read_text()
    src="        let key = (Id::of(self.key_env(env, e)), e);"
    dst="""        // This is also the closure's source-certified contextual support.
        // Retain the source projection rather than recomputing the same one.
        let relevant_env = self.key_env(env, e);
        let key = (Id::of(relevant_env), e);"""
    assert s.count(src)==1,"drift: inference key construction"
    s=s.replace(src,dst)
    src="None => Closure::mk_infer(self.key_env(env, e), ctx, body),"
    dst="None => Closure::mk_infer(relevant_env, ctx, body),"
    assert s.count(src)==1,"drift: lambda dependent closure"
    s=s.replace(src,dst)
    p.write_text(s)

if arm in ("eval","both"):
    p=root/"src/checker/eval.rs"
    s=p.read_text()
    old="                let ce = self.key_env(env, e);"
    new="""                // eval() has already source-projected every open composite
                // into this environment, before entering eval_no_cache().
                // Closed terms still require the original universe-specific
                // lsub base, independently of irrelevant local bindings.
                let ce = if e.num_loose_bvars() == 0 {
                    self.lsub_base(env.lsub())
                } else {
                    env
                };"""
    assert s.count(old)==2, "drift: exact Lambda/Pi evaluation closure sites"
    s=s.replace(old,new)
    p.write_text(s)
print("FLASH_JUDGMENT_FUSION="+arm,flush=True)
