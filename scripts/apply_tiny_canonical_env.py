#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
mode = sys.argv[2] if len(sys.argv) > 2 else "tiny12"
if mode not in {"tiny1", "tiny12"}:
    raise SystemExit(f"unknown mode {mode}")

vpath = root / "src/value.rs"
epath = root / "src/eval.rs"
v = vpath.read_text()
e = epath.read_text()

# Add intrinsically canonical tiny projected-environment variants.  These live in
# the same Env pointer space as Framed, so existing pointer-key caches retain the
# exact semantic identity produced by intern_frame; there is no second pre-key.
needle = '''    Framed {
        mask: u64,
        slots: &'a [V<'a>],
        lsub: Option<&'a LevelSub<'a>>,
        hash: u64,
        len: u32,
        prune: Cell<(u64, Option<E<'a>>)>,
    },
'''
insert = '''    Tiny1 {
        mask: u64,
        v0: V<'a>,
        lsub: Option<&'a LevelSub<'a>>,
        hash: u64,
        len: u32,
        prune: Cell<(u64, Option<E<'a>>)>,
    },
    Tiny2 {
        mask: u64,
        v0: V<'a>,
        v1: V<'a>,
        lsub: Option<&'a LevelSub<'a>>,
        hash: u64,
        len: u32,
        prune: Cell<(u64, Option<E<'a>>)>,
    },
''' + needle
assert needle in v
v = v.replace(needle, insert, 1)

v = v.replace(
'''            Env::Nil { hash, .. } | Env::Cons { hash, .. } | Env::Framed { hash, .. } => *hash,
''',
'''            Env::Nil { hash, .. } | Env::Cons { hash, .. } | Env::Tiny1 { hash, .. }
            | Env::Tiny2 { hash, .. } | Env::Framed { hash, .. } => *hash,
''')
v = v.replace(
'''            Env::Nil { .. } => 0,
            Env::Cons { len, .. } | Env::Framed { len, .. } => *len,
''',
'''            Env::Nil { .. } => 0,
            Env::Cons { len, .. } | Env::Tiny1 { len, .. } | Env::Tiny2 { len, .. }
            | Env::Framed { len, .. } => *len,
''')
v = v.replace(
'''            Env::Nil { lsub, .. } | Env::Cons { lsub, .. } | Env::Framed { lsub, .. } => *lsub,
''',
'''            Env::Nil { lsub, .. } | Env::Cons { lsub, .. } | Env::Tiny1 { lsub, .. }
            | Env::Tiny2 { lsub, .. } | Env::Framed { lsub, .. } => *lsub,
''')

lookup_needle = '''                Env::Framed { mask, slots, .. } => {
                    if idx >= 64 || (mask >> idx) & 1 == 0 {
                        return None;
                    }
                    let below = mask & ((1u64 << idx) - 1);
                    return Some(slots[below.count_ones() as usize]);
                }
'''
lookup_insert = '''                Env::Tiny1 { mask, v0, .. } => {
                    if idx >= 64 || (mask >> idx) & 1 == 0 { return None; }
                    return Some(*v0);
                }
                Env::Tiny2 { mask, v0, v1, .. } => {
                    if idx >= 64 || (mask >> idx) & 1 == 0 { return None; }
                    let below = mask & ((1u64 << idx) - 1);
                    return Some(if below.count_ones() == 0 { *v0 } else { *v1 });
                }
''' + lookup_needle
assert lookup_needle in v
v = v.replace(lookup_needle, lookup_insert, 1)

# Teach the canonical frame interner to intern tiny values directly in Env, avoiding
# the separately allocated slot slice while preserving the exact old hash/equality.
find_needle = '''        if let Some(e) = self.tc_cache.frames.find(hash, |e: &E<'t>| match e {
            value::Env::Framed { mask: m, slots: sl, lsub: l, .. } =>
                *m == mask
                    && l.map_or(0, |l| l as *const value::LevelSub<'t> as usize) == lsub_addr
                    && sl.len() == slots.len()
                    && sl.iter().zip(slots).all(|(a, b)| std::ptr::eq(*a, *b)),
            _ => false,
        }) {
'''
find_repl = '''        if let Some(e) = self.tc_cache.frames.find(hash, |e: &E<'t>| match e {
            value::Env::Tiny1 { mask: m, v0, lsub: l, .. } =>
                slots.len() == 1 && *m == mask
                    && l.map_or(0, |l| l as *const value::LevelSub<'t> as usize) == lsub_addr
                    && std::ptr::eq(*v0, slots[0]),
            value::Env::Tiny2 { mask: m, v0, v1, lsub: l, .. } =>
                slots.len() == 2 && *m == mask
                    && l.map_or(0, |l| l as *const value::LevelSub<'t> as usize) == lsub_addr
                    && std::ptr::eq(*v0, slots[0]) && std::ptr::eq(*v1, slots[1]),
            value::Env::Framed { mask: m, slots: sl, lsub: l, .. } =>
                *m == mask
                    && l.map_or(0, |l| l as *const value::LevelSub<'t> as usize) == lsub_addr
                    && sl.len() == slots.len()
                    && sl.iter().zip(slots).all(|(a, b)| std::ptr::eq(*a, *b)),
            _ => false,
        }) {
'''
assert find_needle in e
e = e.replace(find_needle, find_repl, 1)

alloc_needle = '''        let len = 64 - mask.leading_zeros();
        let e: E<'t> = self.arena.alloc(value::Env::Framed {
            mask,
            slots: self.arena.alloc_slice_copy(slots),
            lsub,
            hash,
            len,
            prune: std::cell::Cell::new((0, None)),
        });
'''
if mode == "tiny1":
    alloc_repl = '''        let len = 64 - mask.leading_zeros();
        let e: E<'t> = if slots.len() == 1 {
            self.arena.alloc(value::Env::Tiny1 { mask, v0: slots[0], lsub, hash, len,
                prune: std::cell::Cell::new((0, None)) })
        } else {
            self.arena.alloc(value::Env::Framed { mask, slots: self.arena.alloc_slice_copy(slots),
                lsub, hash, len, prune: std::cell::Cell::new((0, None)) })
        };
'''
else:
    alloc_repl = '''        let len = 64 - mask.leading_zeros();
        let e: E<'t> = match slots.len() {
            1 => self.arena.alloc(value::Env::Tiny1 { mask, v0: slots[0], lsub, hash, len,
                prune: std::cell::Cell::new((0, None)) }),
            2 => self.arena.alloc(value::Env::Tiny2 { mask, v0: slots[0], v1: slots[1], lsub, hash, len,
                prune: std::cell::Cell::new((0, None)) }),
            _ => self.arena.alloc(value::Env::Framed { mask, slots: self.arena.alloc_slice_copy(slots),
                lsub, hash, len, prune: std::cell::Cell::new((0, None)) }),
        };
'''
assert alloc_needle in e
e = e.replace(alloc_needle, alloc_repl, 1)

# Fast prune handling for all canonical projected variants.
prune_needle = '''            value::Env::Framed { mask: m, prune, .. } => {
                if *m & mask == *m {
                    return e
                }
                let (m, r) = prune.get();
                if m == mask {
                    if let Some(r) = r {
                        return r;
                    }
                }
            }
'''
prune_repl = '''            value::Env::Tiny1 { mask: m, prune, .. }
            | value::Env::Tiny2 { mask: m, prune, .. }
            | value::Env::Framed { mask: m, prune, .. } => {
                if *m & mask == *m { return e }
                let (m, r) = prune.get();
                if m == mask { if let Some(r) = r { return r; } }
            }
'''
assert prune_needle in e
e = e.replace(prune_needle, prune_repl, 1)

# Direct-map hit propagation.
e = e.replace(
'''                    value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } =>
                        prune.set((mask, Some(hit))),
''',
'''                    value::Env::Cons { prune, .. } | value::Env::Tiny1 { prune, .. }
                    | value::Env::Tiny2 { prune, .. } | value::Env::Framed { prune, .. } =>
                        prune.set((mask, Some(hit))),
''')

# Cold traversal can consume a tiny canonical root without reconstructing a slice.
framed_cold = '''                value::Env::Framed { mask: fmask, slots, .. } => {
                    let limit = 64 - consumed;
                    let bound = if limit >= 64 { u64::MAX } else { (1u64 << limit) - 1 };
                    let m2 = rem & *fmask & bound;
                    out_mask |= m2 << consumed;
                    let mut sel = select_ranks(m2, *fmask);
                    while sel != 0 {
                        let i = sel.trailing_zeros() as usize;
                        sel &= sel - 1;
                        let sv = slots[i];
                        buf[n].write(sv);
                        slots_hash = slots_hash
                            .wrapping_mul(0x9E3779B97F4A7C15)
                            .wrapping_add(sv as *const Value<'t> as usize as u64);
                        n += 1;
                    }
                    break;
                }
'''
tiny_cold = '''                value::Env::Tiny1 { mask: fmask, v0, .. } => {
                    let limit = 64 - consumed;
                    let bound = if limit >= 64 { u64::MAX } else { (1u64 << limit) - 1 };
                    let m2 = rem & *fmask & bound;
                    out_mask |= m2 << consumed;
                    if m2 != 0 {
                        let sv = *v0; buf[n].write(sv);
                        slots_hash = slots_hash.wrapping_mul(0x9E3779B97F4A7C15)
                            .wrapping_add(sv as *const Value<'t> as usize as u64); n += 1;
                    }
                    break;
                }
                value::Env::Tiny2 { mask: fmask, v0, v1, .. } => {
                    let limit = 64 - consumed;
                    let bound = if limit >= 64 { u64::MAX } else { (1u64 << limit) - 1 };
                    let m2 = rem & *fmask & bound;
                    out_mask |= m2 << consumed;
                    let vals = [*v0, *v1];
                    let mut sel = select_ranks(m2, *fmask);
                    while sel != 0 {
                        let i = sel.trailing_zeros() as usize; sel &= sel - 1;
                        let sv = vals[i]; buf[n].write(sv);
                        slots_hash = slots_hash.wrapping_mul(0x9E3779B97F4A7C15)
                            .wrapping_add(sv as *const Value<'t> as usize as u64); n += 1;
                    }
                    break;
                }
''' + framed_cold
assert framed_cold in e
e = e.replace(framed_cold, tiny_cold, 1)

e = e.replace(
'''            value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } => prune.set((mask, Some(r))),
''',
'''            value::Env::Cons { prune, .. } | value::Env::Tiny1 { prune, .. }
            | value::Env::Tiny2 { prune, .. } | value::Env::Framed { prune, .. } => prune.set((mask, Some(r))),
''')

vpath.write_text(v)
epath.write_text(e)
print(f"applied intrinsically canonical env mode={mode}")
