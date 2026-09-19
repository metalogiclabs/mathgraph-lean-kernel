#!/usr/bin/env python3
from pathlib import Path

p = Path("src/eval.rs")
c = p.read_text()

start = """        let wanted = self.wide_fvars(e);
        let mut indices = smallvec::SmallVec::<[u16; 16]>::new();
        let mut slots = smallvec::SmallVec::<[V<'t>; 16]>::new();
        let mut cur = env;
        let mut consumed = 0;
        let lsub = env.lsub();
        let mut slots_hash = lsub.map_or(0, |l| l as *const value::LevelSub<'t> as usize as u64);
        for &idx in wanted {
            while consumed < idx {
                let value::Env::Cons { parent, .. } = cur else { break };
                cur = parent;
                consumed += 1;
            }
            if let Some(v) = cur.lookup(idx - consumed) {
                indices.push(idx);
                slots.push(v);
                slots_hash =
                    slots_hash.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(v as *const Value<'t> as usize as u64);
            }
        }
"""

replacement = """        let wanted = self.wide_fvars(e);
        let mut indices = smallvec::SmallVec::<[u16; 16]>::new();
        let mut slots = smallvec::SmallVec::<[V<'t>; 16]>::new();
        let mut cur = env;
        let mut consumed: u16 = 0;
        let lsub = env.lsub();
        let mut slots_hash = lsub.map_or(0, |l| l as *const value::LevelSub<'t> as usize as u64);
        let mut pos = 0usize;

        while pos < wanted.len() {
            match cur {
                value::Env::Nil { .. } => break,
                value::Env::Cons { v, parent, .. } => {
                    let idx = wanted[pos];
                    if idx < consumed {
                        pos += 1;
                        continue;
                    }
                    if consumed < idx {
                        cur = parent;
                        consumed += 1;
                        continue;
                    }
                    indices.push(idx);
                    slots.push(*v);
                    slots_hash = slots_hash
                        .wrapping_mul(0x9E3779B97F4A7C15)
                        .wrapping_add(*v as *const Value<'t> as usize as u64);
                    pos += 1;
                }
                value::Env::Framed { mask, slots: frame_slots, .. } => {
                    for &idx in &wanted[pos..] {
                        let Some(rel) = idx.checked_sub(consumed) else { continue };
                        if rel >= 64 || ((*mask >> rel) & 1) == 0 {
                            continue;
                        }
                        let below = if rel == 0 { 0 } else { *mask & ((1u64 << rel) - 1) };
                        let v = frame_slots[below.count_ones() as usize];
                        indices.push(idx);
                        slots.push(v);
                        slots_hash = slots_hash
                            .wrapping_mul(0x9E3779B97F4A7C15)
                            .wrapping_add(v as *const Value<'t> as usize as u64);
                    }
                    break;
                }
                value::Env::WideFramed { data, .. } => {
                    let mut wi = pos;
                    let mut fi = 0usize;
                    while wi < wanted.len() && fi < data.indices.len() {
                        let Some(rel) = wanted[wi].checked_sub(consumed) else {
                            wi += 1;
                            continue;
                        };
                        let frame_idx = data.indices[fi];
                        if rel < frame_idx {
                            wi += 1;
                        } else if rel > frame_idx {
                            fi += 1;
                        } else {
                            let v = data.slots[fi];
                            indices.push(wanted[wi]);
                            slots.push(v);
                            slots_hash = slots_hash
                                .wrapping_mul(0x9E3779B97F4A7C15)
                                .wrapping_add(v as *const Value<'t> as usize as u64);
                            wi += 1;
                            fi += 1;
                        }
                    }
                    break;
                }
            }
        }
"""

n = c.count(start)
if n != 1:
    raise SystemExit(f"expected one wide projection anchor, found {n}")
c = c.replace(start, replacement, 1)
p.write_text(c)
print("FLASH_WIDE_ONEPASS_PATCH=PASS")
