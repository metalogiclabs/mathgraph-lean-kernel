#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])

vp=root/'src/value.rs'
s=vp.read_text()
old='''    Framed {\n        mask: u64,\n        slots: &'a [V<'a>],\n        lsub: Option<&'a LevelSub<'a>>,\n        hash: u64,\n        len: u32,\n        prune: Cell<(u64, Option<E<'a>>)>,\n    },\n}'''
new='''    Framed {\n        mask: u64,\n        slots: &'a [V<'a>],\n        lsub: Option<&'a LevelSub<'a>>,\n        hash: u64,\n        len: u32,\n        prune: Cell<(u64, Option<E<'a>>)>,\n    },\n    // A zero-copy subprojection of an already materialized frame.\n    // `mask` remains in the original de Bruijn coordinate system.\n    Projected {\n        base: E<'a>,\n        mask: u64,\n        lsub: Option<&'a LevelSub<'a>>,\n        hash: u64,\n        len: u32,\n        prune: Cell<(u64, Option<E<'a>>)>,\n    },\n}'''
assert old in s
s=s.replace(old,new,1)
s=s.replace('Env::Nil { hash, .. } | Env::Cons { hash, .. } | Env::Framed { hash, .. } => *hash,',
            'Env::Nil { hash, .. } | Env::Cons { hash, .. } | Env::Framed { hash, .. } | Env::Projected { hash, .. } => *hash,')
s=s.replace('Env::Cons { len, .. } | Env::Framed { len, .. } => *len,',
            'Env::Cons { len, .. } | Env::Framed { len, .. } | Env::Projected { len, .. } => *len,')
s=s.replace('Env::Nil { lsub, .. } | Env::Cons { lsub, .. } | Env::Framed { lsub, .. } => *lsub,',
            'Env::Nil { lsub, .. } | Env::Cons { lsub, .. } | Env::Framed { lsub, .. } | Env::Projected { lsub, .. } => *lsub,')
old_lookup='''                Env::Framed { mask, slots, .. } => {\n                    if idx >= 64 || (mask >> idx) & 1 == 0 {\n                        return None;\n                    }\n                    let below = mask & ((1u64 << idx) - 1);\n                    return Some(slots[below.count_ones() as usize]);\n                }'''
new_lookup='''                Env::Framed { mask, slots, .. } => {\n                    if idx >= 64 || (mask >> idx) & 1 == 0 {\n                        return None;\n                    }\n                    let below = mask & ((1u64 << idx) - 1);\n                    return Some(slots[below.count_ones() as usize]);\n                }\n                Env::Projected { base, mask, .. } => {\n                    if idx >= 64 || (mask >> idx) & 1 == 0 {\n                        return None;\n                    }\n                    return base.lookup(idx);\n                }'''
assert old_lookup in s
s=s.replace(old_lookup,new_lookup,1)
vp.write_text(s)

ep=root/'src/eval.rs'
s=ep.read_text()
# allow frame interning predicate to ignore projected values naturally; no change needed there.
old='''            value::Env::Framed { mask: m, prune, .. } => {\n                if *m & mask == *m {\n                    return e\n                }\n                let (m, r) = prune.get();\n                if m == mask {\n                    if let Some(r) = r {\n                        return r;\n                    }\n                }\n            }\n            value::Env::Cons { prune, .. } => {'''
new='''            value::Env::Framed { mask: m, prune, .. } => {\n                if *m & mask == *m {\n                    return e\n                }\n                let (cm, r) = prune.get();\n                if cm == mask {\n                    if let Some(r) = r {\n                        return r;\n                    }\n                }\n                // v23: compose the projection symbolically instead of selecting,\n                // copying, hashing and interning another frame immediately.\n                let pmask = *m & mask;\n                if pmask == 0 {\n                    return self.lsub_base(e.lsub());\n                }\n                let len = 64 - pmask.leading_zeros();\n                let hash = e.get_hash().wrapping_mul(0xD6E8FEB86659FD93).wrapping_add(pmask);\n                let r: E<'t> = self.arena.alloc(value::Env::Projected {\n                    base: e, mask: pmask, lsub: e.lsub(), hash, len,\n                    prune: std::cell::Cell::new((0, None)),\n                });\n                prune.set((mask, Some(r)));\n                return r;\n            }\n            value::Env::Projected { base, mask: m, prune, .. } => {\n                if *m & mask == *m {\n                    return e\n                }\n                let (cm, r) = prune.get();\n                if cm == mask {\n                    if let Some(r) = r {\n                        return r;\n                    }\n                }\n                let pmask = *m & mask;\n                if pmask == 0 {\n                    return self.lsub_base(e.lsub());\n                }\n                let len = 64 - pmask.leading_zeros();\n                let hash = base.get_hash().wrapping_mul(0xD6E8FEB86659FD93).wrapping_add(pmask);\n                let r: E<'t> = self.arena.alloc(value::Env::Projected {\n                    base: *base, mask: pmask, lsub: e.lsub(), hash, len,\n                    prune: std::cell::Cell::new((0, None)),\n                });\n                prune.set((mask, Some(r)));\n                return r;\n            }\n            value::Env::Cons { prune, .. } => {'''
assert old in s
s=s.replace(old,new,1)
s=s.replace('value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } =>\n                        prune.set((mask, Some(hit))),',
            'value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } | value::Env::Projected { prune, .. } =>\n                        prune.set((mask, Some(hit))),')
s=s.replace('value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } => prune.set((mask, Some(r))),',
            'value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } | value::Env::Projected { prune, .. } => prune.set((mask, Some(r))),')
# Defensive cold-path support if a Projected env reaches it through future code.
needle='''                value::Env::Framed { mask: fmask, slots, .. } => {\n                    let limit = 64 - consumed;'''
replacement='''                value::Env::Projected { base, mask: fmask, .. } => {\n                    let limit = 64 - consumed;\n                    let bound = if limit >= 64 { u64::MAX } else { (1u64 << limit) - 1 };\n                    let m2 = rem & *fmask & bound;\n                    out_mask |= m2 << consumed;\n                    let mut bits = m2;\n                    while bits != 0 {\n                        let idx = bits.trailing_zeros() as u16;\n                        bits &= bits - 1;\n                        if let Some(sv) = base.lookup(idx) {\n                            buf[n].write(sv);\n                            slots_hash = slots_hash.wrapping_mul(0x9E3779B97F4A7C15)\n                                .wrapping_add(sv as *const Value<'t> as usize as u64);\n                            n += 1;\n                        }\n                    }\n                    break;\n                }\n                value::Env::Framed { mask: fmask, slots, .. } => {\n                    let limit = 64 - consumed;'''
assert needle in s
s=s.replace(needle,replacement,1)
ep.write_text(s)
print('V23_LAZY_FRAMED_SUBPROJECTION_PATCH=APPLIED')
