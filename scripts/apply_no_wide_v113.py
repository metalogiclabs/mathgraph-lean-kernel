#!/usr/bin/env python3
from pathlib import Path
p=Path("src/eval.rs")
c=p.read_text()
old="""        if k > 64 {
            let ck = (env as *const value::Env<'t> as usize, e);
            if let Some(r) = self.tc_cache.wide_prune_cache.get(&ck) {
                return *r;
            }
            let Some(words) = self.exact_wide_uses(e) else { return env };
            let r = self.prune_env_wide(env, &words);
            self.tc_cache.wide_prune_cache.insert(ck, r);
            return r;
        }"""
new="""        if k > 64 {
            return env;
        }"""
n=c.count(old)
if n!=1:
    raise SystemExit(f"v113 key_env anchor count={n}")
p.write_text(c.replace(old,new,1))
print("APPLY_NO_WIDE_V113=PASS")
