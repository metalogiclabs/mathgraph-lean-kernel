#!/usr/bin/env python3
"""Single-pass insertion for frequently repeated closed semantics of env_extend.

The pinned TypeChecker::env_extend gets the same (parent,value) key twice on
MISS: a PtrMap.get() followed by PtrMap.insert(). Both probe the same table.
The intervening value::env_extend is a pure single Bump allocation of Env::Cons
which does not touch the table and cannot displace the vacant slot. Reuse
find()'s vacant slot through insert_at().  A hit returns the same interned
environment, a miss creates the same Env::Cons, with no proof or typing change.
Do NOT generalize this rewrite to recursively computed memo entries.
"""
from pathlib import Path
import sys
p=Path(sys.argv[1])/"src/checker/eval/environment.rs"
s=p.read_text()
old="""    #[inline(always)]
    pub(crate) fn env_extend(&mut self, parent: E<'t>, v: V<'t>) -> E<'t> {
        match self.tc_cache.env_hc.get(&(Id::of(parent), Id::of(v))) {
            Some(e) => e,
            None => self.env_new(parent, v),
        }
    }

    #[inline(never)]
    fn env_new(&mut self, parent: E<'t>, v: V<'t>) -> E<'t> {
        let e = value::env_extend(self.arena, parent, v);
        self.tc_cache.env_hc.insert((Id::of(parent), Id::of(v)), e);
        e
    }
"""
new="""    #[inline(always)]
    pub(crate) fn env_extend(&mut self, parent: E<'t>, v: V<'t>) -> E<'t> {
        // The miss constructor only allocates an Env::Cons; it never mutates
        // env_hc. Preserve the first probe's vacant slot for insertion.
        match self.tc_cache.env_hc.find((Id::of(parent), Id::of(v))) {
            Ok(e) => e,
            Err(at) => self.env_new_at(parent, v, at),
        }
    }

    #[inline(never)]
    fn env_new_at(&mut self, parent: E<'t>, v: V<'t>, at: (usize, u8)) -> E<'t> {
        let e = value::env_extend(self.arena, parent, v);
        self.tc_cache
            .env_hc
            .insert_at(at, (Id::of(parent), Id::of(v)), e);
        e
    }
"""
assert s.count(old)==1, "Pinned env_extend implementation does not match"
assert s.count("self.env_new(parent, v)")==1
assert s.count("fn env_new(")==1
s=s.replace(old,new)
p.write_text(s)
print("ENV_EXTEND_SINGLE_PROBE=APPLIED_NO_REENTRANT_MAP_WRITES",flush=True)
