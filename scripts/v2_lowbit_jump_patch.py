from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / "src/value.rs"
s = p.read_text()

old_enum = "    Cons {\n        v: V<'a>,\n        parent: E<'a>,\n        lsub: Option<&'a LevelSub<'a>>,\n        hash: u64,\n        len: u32,\n        prune: Cell<(u64, Option<E<'a>>)>,\n    },"
new_enum = "    Cons {\n        v: V<'a>,\n        parent: E<'a>,\n        jump: E<'a>,\n        jump_dist: u32,\n        lsub: Option<&'a LevelSub<'a>>,\n        hash: u64,\n        len: u32,\n        prune: Cell<(u64, Option<E<'a>>)>,\n    },"
assert old_enum in s
s = s.replace(old_enum, new_enum, 1)

old_lookup = "    pub fn lookup(&self, mut idx: u16) -> Option<V<'a>> {\n        let mut cur = self;\n        loop {\n            match cur {\n                Env::Nil { .. } => return None,\n                Env::Cons { v, parent, .. } => {\n                    if idx == 0 {\n                        return Some(*v);\n                    }\n                    idx -= 1;\n                    cur = parent;\n                }"
new_lookup = "    pub fn lookup(&self, idx: u16) -> Option<V<'a>> {\n        let mut idx = u32::from(idx);\n        let mut cur = self;\n        loop {\n            match cur {\n                Env::Nil { .. } => return None,\n                Env::Cons { v, parent, jump, jump_dist, .. } => {\n                    if idx == 0 {\n                        return Some(*v);\n                    }\n                    if *jump_dist <= idx {\n                        idx -= *jump_dist;\n                        cur = jump;\n                    } else {\n                        idx -= 1;\n                        cur = parent;\n                    }\n                }"
assert old_lookup in s
s = s.replace(old_lookup, new_lookup, 1)

old_extend = "pub fn env_extend<'a>(arena: &'a Bump, parent: E<'a>, v: V<'a>) -> E<'a> {\n    let v_hash = v as *const Value<'a> as usize as u64;\n    let parent_hash = parent.get_hash();\n    let hash = parent_hash.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(v_hash);\n    arena.alloc(Env::Cons {\n        v,\n        parent,\n        lsub: parent.lsub(),\n        hash,\n        len: parent.len() + 1,\n        prune: Cell::new((0, None)),\n    })\n}"
new_extend = "pub fn env_extend<'a>(arena: &'a Bump, parent: E<'a>, v: V<'a>) -> E<'a> {\n    let v_hash = v as *const Value<'a> as usize as u64;\n    let parent_hash = parent.get_hash();\n    let hash = parent_hash.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(v_hash);\n    let len = parent.len() + 1;\n\n    // One deterministic skip pointer per node. Its span is the largest power\n    // of two dividing this node's depth. This gives logarithmic ancestor\n    // navigation while keeping persistent extension compact. A framed parent\n    // is an intentional terminal representation, so do not manufacture a\n    // shortcut through it.\n    let mut jump_dist = len & len.wrapping_neg();\n    if matches!(parent, Env::Framed { .. }) {\n        jump_dist = 1;\n    }\n    let mut jump = parent;\n    let mut remaining = jump_dist - 1;\n    while remaining != 0 {\n        match jump {\n            Env::Cons { jump: jj, jump_dist: jd, .. } if *jd <= remaining => {\n                remaining -= *jd;\n                jump = jj;\n            }\n            Env::Cons { parent: jp, .. } => {\n                remaining -= 1;\n                jump = jp;\n            }\n            Env::Nil { .. } | Env::Framed { .. } => {\n                jump_dist = 1;\n                jump = parent;\n                break;\n            }\n        }\n    }\n\n    arena.alloc(Env::Cons {\n        v,\n        parent,\n        jump,\n        jump_dist,\n        lsub: parent.lsub(),\n        hash,\n        len,\n        prune: Cell::new((0, None)),\n    })\n}"
assert old_extend in s
s = s.replace(old_extend, new_extend, 1)

p.write_text(s)
