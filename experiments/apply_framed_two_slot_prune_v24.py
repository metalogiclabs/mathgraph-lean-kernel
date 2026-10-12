#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])

vp=root/'src/value.rs'
s=vp.read_text()
old='''    Framed {\n        mask: u64,\n        slots: &'a [V<'a>],\n        lsub: Option<&'a LevelSub<'a>>,\n        hash: u64,\n        len: u32,\n        prune: Cell<(u64, Option<E<'a>>)>,\n    },'''
new='''    Framed {\n        mask: u64,\n        slots: &'a [V<'a>],\n        lsub: Option<&'a LevelSub<'a>>,\n        hash: u64,\n        len: u32,\n        prune: Cell<(u64, Option<E<'a>>)>,\n        // v24: retain one additional fully materialized subprojection.\n        // This targets A→B→A mask thrashing without changing lookup representation.\n        prune2: Cell<(u64, Option<E<'a>>)>,\n    },'''
assert s.count(old)==1, s.count(old)
s=s.replace(old,new,1)
vp.write_text(s)

ep=root/'src/eval.rs'
s=ep.read_text()
old_ctor='''            len,\n            prune: std::cell::Cell::new((0, None)),\n        });'''
new_ctor='''            len,\n            prune: std::cell::Cell::new((0, None)),\n            prune2: std::cell::Cell::new((0, None)),\n        });'''
assert s.count(old_ctor)==1, s.count(old_ctor)
s=s.replace(old_ctor,new_ctor,1)

old_fast='''            value::Env::Framed { mask: m, prune, .. } => {\n                if *m & mask == *m {\n                    return e\n                }\n                let (m, r) = prune.get();\n                if m == mask {\n                    if let Some(r) = r {\n                        return r;\n                    }\n                }\n            }'''
new_fast='''            value::Env::Framed { mask: m, prune, prune2, .. } => {\n                if *m & mask == *m {\n                    return e\n                }\n                let (m1, r1) = prune.get();\n                if m1 == mask {\n                    if let Some(r) = r1 {\n                        return r;\n                    }\n                }\n                let (m2, r2) = prune2.get();\n                if m2 == mask {\n                    if let Some(r) = r2 {\n                        // Promote the hit so the two slots behave as a tiny source-local LRU.\n                        prune2.set((m1, r1));\n                        prune.set((m2, r2));\n                        return r;\n                    }\n                }\n            }'''
assert s.count(old_fast)==1, s.count(old_fast)
s=s.replace(old_fast,new_fast,1)

old_dm='''                match e {\n                    value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } =>\n                        prune.set((mask, Some(hit))),\n                    value::Env::Nil { .. } => {}\n                }'''
new_dm='''                match e {\n                    value::Env::Cons { prune, .. } => prune.set((mask, Some(hit))),\n                    value::Env::Framed { prune, prune2, .. } => {\n                        prune2.set(prune.get());\n                        prune.set((mask, Some(hit)));\n                    }\n                    value::Env::Nil { .. } => {}\n                }'''
assert s.count(old_dm)==1, s.count(old_dm)
s=s.replace(old_dm,new_dm,1)

old_publish='''        match e {\n            value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } => prune.set((mask, Some(r))),\n            value::Env::Nil { .. } => {}\n        }'''
new_publish='''        match e {\n            value::Env::Cons { prune, .. } => prune.set((mask, Some(r))),\n            value::Env::Framed { prune, prune2, .. } => {\n                prune2.set(prune.get());\n                prune.set((mask, Some(r)));\n            }\n            value::Env::Nil { .. } => {}\n        }'''
assert s.count(old_publish)==1, s.count(old_publish)
s=s.replace(old_publish,new_publish,1)
ep.write_text(s)
print('V24_FRAMED_TWO_SLOT_PRUNE_PATCH=APPLIED')
