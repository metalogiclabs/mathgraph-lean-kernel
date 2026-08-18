from pathlib import Path
import sys

root = Path(sys.argv[1])

# Phase-change candidate: preserve key semantics while replacing repeated
# env.lookup(i) walks (quadratic on Cons chains) with one linear traversal.

vp = root / "src/value.rs"
vs = vp.read_text()
old_value = '''fn env_slots_key(env: E<'_>, count: u16) -> (u64, bool) {
    let mut d = lsub_key(env.lsub());
    let mut closed = true;
    for i in 0..count {
        if let Some(v) = env.lookup(i) {
            d = kmix(kmix(d, u64::from(i)), v.digest());
            closed &= v.is_closed();
        }
    }
    (d, closed)
}'''
new_value = '''fn env_slots_key(env: E<'_>, count: u16) -> (u64, bool) {
    let mut d = lsub_key(env.lsub());
    let mut closed = true;
    let mut cur = env;
    let mut base = 0u16;
    while base < count {
        match cur {
            Env::Nil { .. } => break,
            Env::Cons { v, parent, .. } => {
                d = kmix(kmix(d, u64::from(base)), v.digest());
                closed &= v.is_closed();
                base += 1;
                cur = parent;
            }
            Env::Framed { mask, slots, .. } => {
                let rem = u32::from(count - base);
                let bound = if rem >= 64 { u64::MAX } else { (1u64 << rem) - 1 };
                let mut selected = *mask & bound;
                while selected != 0 {
                    let rel = selected.trailing_zeros();
                    selected &= selected - 1;
                    let below = *mask & if rel == 0 { 0 } else { (1u64 << rel) - 1 };
                    let v = slots[below.count_ones() as usize];
                    let i = base + rel as u16;
                    d = kmix(kmix(d, u64::from(i)), v.digest());
                    closed &= v.is_closed();
                }
                break;
            }
        }
    }
    (d, closed)
}'''
assert old_value in vs, "value.rs env_slots_key shape changed"
vp.write_text(vs.replace(old_value, new_value, 1))

ep = root / "src/eval.rs"
es = ep.read_text()
old_eval = '''    fn env_key(&mut self, acc: u128, closed: bool, env: E<'t>, depth: u32, count: u16) -> Result<(u128, bool), u8> {
        let mut acc = acc;
        let mut closed = closed;
        if let Some(ls) = env.lsub() {
            acc = mix(mix(acc, u128::from(ls.ks.get_hash())), u128::from(ls.vs.get_hash()));
        }
        for i in 0..count {
            if let Some(slot) = env.lookup(i) {
                let (k, c) = self.global_key(slot, depth)?;
                acc = mix(mix(acc, u128::from(i)), k);
                closed &= c;
            }
        }
        Ok((acc, closed))
    }'''
new_eval = '''    fn env_key(&mut self, acc: u128, closed: bool, env: E<'t>, depth: u32, count: u16) -> Result<(u128, bool), u8> {
        let mut acc = acc;
        let mut closed = closed;
        if let Some(ls) = env.lsub() {
            acc = mix(mix(acc, u128::from(ls.ks.get_hash())), u128::from(ls.vs.get_hash()));
        }
        let mut cur = env;
        let mut base = 0u16;
        while base < count {
            match cur {
                value::Env::Nil { .. } => break,
                value::Env::Cons { v, parent, .. } => {
                    let (k, c) = self.global_key(*v, depth)?;
                    acc = mix(mix(acc, u128::from(base)), k);
                    closed &= c;
                    base += 1;
                    cur = parent;
                }
                value::Env::Framed { mask, slots, .. } => {
                    let rem = u32::from(count - base);
                    let bound = if rem >= 64 { u64::MAX } else { (1u64 << rem) - 1 };
                    let mut selected = *mask & bound;
                    while selected != 0 {
                        let rel = selected.trailing_zeros();
                        selected &= selected - 1;
                        let below = *mask & if rel == 0 { 0 } else { (1u64 << rel) - 1 };
                        let slot = slots[below.count_ones() as usize];
                        let i = base + rel as u16;
                        let (k, c) = self.global_key(slot, depth)?;
                        acc = mix(mix(acc, u128::from(i)), k);
                        closed &= c;
                    }
                    break;
                }
            }
        }
        Ok((acc, closed))
    }'''
assert old_eval in es, "eval.rs env_key shape changed"
ep.write_text(es.replace(old_eval, new_eval, 1))
