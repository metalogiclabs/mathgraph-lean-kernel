#!/usr/bin/env python3
"""Preserve PtrMap find() vacancy through pure source-constant head creation.

The original eval_const() probes const_head_value_cache on miss and then
probes it again in insert(). The intervening body only creates the constant
head: get_declar, alloc OnceCell, mk_head_hc in a *different* rigid_hc cache,
mark canonical. No access can insert into const_head_value_cache.
Therefore a cache miss can reuse find()'s vacant slot via insert_at,
without altering any value, proof, axiom or invalid rejection.
"""
from pathlib import Path
import sys
p=Path(sys.argv[1])/"src/checker/eval.rs"
s=p.read_text()
a=s.index("    pub(crate) fn eval_const(")
b=s.index("    pub(crate) fn const_result_level(",a)
block=s[a:b]
old_get="""        if let Some(cached) = self.tc_cache.const_head_value_cache.get(&(name, levels)) {
            return cached;
        }"""
new_get="""        // No writes to this same map occur while constructing a Const head;
        // keep the first miss probe's vacant slot rather than rehashing.
        let vacant = match self.tc_cache.const_head_value_cache.find((name, levels)) {
            Ok(cached) => return cached,
            Err(vacant) => vacant,
        };"""
old_insert="""        self.tc_cache
            .const_head_value_cache
            .insert((name, levels), v);"""
new_insert="""        self.tc_cache
            .const_head_value_cache
            .insert_at(vacant, (name, levels), v);"""
assert block.count(old_get)==1 and block.count(old_insert)==1
assert block.count("self.const_head_type(")==0, "Avoid proof-dependent evaluation on miss"
block=block.replace(old_get,new_get).replace(old_insert,new_insert)
s=s[:a]+block+s[b:]
p.write_text(s)
print("CONST_HEAD_SINGLE_PROBE=APPLIED_CANONICAL_EQUIVALENT",flush=True)
