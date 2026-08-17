from pathlib import Path

STRIDE = 32
p = Path("src/value.rs")
s = p.read_text()

old_enum = "    Cons {\n        v: V<'a>,\n        parent: E<'a>,\n        lsub: Option<&'a LevelSub<'a>>,\n        hash: u64,\n        len: u32,\n        prune: Cell<(u64, Option<E<'a>>)>,\n    },"
new_enum = "    Cons {\n        v: V<'a>,\n        parent: E<'a>,\n        jump: Option<E<'a>>,\n        lsub: Option<&'a LevelSub<'a>>,\n        hash: u64,\n        len: u32,\n        prune: Cell<(u64, Option<E<'a>>)>,\n    },"
assert old_enum in s
s = s.replace(old_enum, new_enum, 1)

old_lookup = "                Env::Cons { v, parent, .. } => {\n                    if idx == 0 {\n                        return Some(*v);\n                    }\n                    idx -= 1;\n                    cur = parent;\n                }"
new_lookup = f"                Env::Cons {{ v, parent, jump, .. }} => {{\n                    if idx == 0 {{\n                        return Some(*v);\n                    }}\n                    if idx >= {STRIDE} {{\n                        if let Some(j) = jump {{\n                            idx -= {STRIDE};\n                            cur = j;\n                            continue;\n                        }}\n                    }}\n                    idx -= 1;\n                    cur = parent;\n                }}"
assert old_lookup in s
s = s.replace(old_lookup, new_lookup, 1)

old_extend = "pub fn env_extend<'a>(arena: &'a Bump, parent: E<'a>, v: V<'a>) -> E<'a> {\n    let v_hash = v as *const Value<'a> as usize as u64;\n    let parent_hash = parent.get_hash();\n    let hash = parent_hash.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(v_hash);\n    arena.alloc(Env::Cons {\n        v,\n        parent,\n        lsub: parent.lsub(),\n        hash,\n        len: parent.len() + 1,\n        prune: Cell::new((0, None)),\n    })\n}"
new_extend = f"pub fn env_extend<'a>(arena: &'a Bump, parent: E<'a>, v: V<'a>) -> E<'a> {{\n    let v_hash = v as *const Value<'a> as usize as u64;\n    let parent_hash = parent.get_hash();\n    let hash = parent_hash.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(v_hash);\n    let mut jump = Some(parent);\n    for _ in 1..{STRIDE} {{\n        jump = match jump {{\n            Some(Env::Cons {{ parent, .. }}) => Some(*parent),\n            _ => None,\n        }};\n        if jump.is_none() {{ break; }}\n    }}\n    arena.alloc(Env::Cons {{\n        v,\n        parent,\n        jump,\n        lsub: parent.lsub(),\n        hash,\n        len: parent.len() + 1,\n        prune: Cell::new((0, None)),\n    }})\n}}"
assert old_extend in s
s = s.replace(old_extend, new_extend, 1)

p.write_text(s)
