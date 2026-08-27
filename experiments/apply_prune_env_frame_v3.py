from pathlib import Path

p = Path('src/value.rs')
s = p.read_text()
old = '''pub fn env_extend<'a>(arena: &'a Bump, parent: E<'a>, v: V<'a>) -> E<'a> {
    let v_hash = v as *const Value<'a> as usize as u64;
    let parent_hash = parent.get_hash();
    let hash = parent_hash.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(v_hash);
    arena.alloc(Env::Cons {
        v,
        parent,
        lsub: parent.lsub(),
        hash,
        len: parent.len() + 1,
        prune: Cell::new((0, None)),
    })
}
'''
new = '''pub fn env_extend<'a>(arena: &'a Bump, parent: E<'a>, v: V<'a>) -> E<'a> {
    let v_hash = v as *const Value<'a> as usize as u64;
    let parent_hash = parent.get_hash();
    let hash = parent_hash.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(v_hash);
    let len = parent.len() + 1;

    // Phase-change probe: for the <=64 slot regime used by prune_env, carry the
    // environment as a dense indexed frame from construction time rather than
    // rebuilding it from a linked Cons chain on every cold prune.  Slot order
    // follows Env::lookup: bit/slot 0 is the newest binding.
    if len <= 64 {
        let mut slots = Vec::with_capacity(len as usize);
        slots.push(v);
        for i in 0..parent.len() {
            let Some(pv) = parent.lookup(i as u16) else { break };
            slots.push(pv);
        }
        let mask = if len == 64 { u64::MAX } else { (1u64 << len) - 1 };
        return arena.alloc(Env::Framed {
            mask,
            slots: arena.alloc_slice_copy(&slots),
            lsub: parent.lsub(),
            hash,
            len,
            prune: Cell::new((0, None)),
        });
    }

    arena.alloc(Env::Cons {
        v,
        parent,
        lsub: parent.lsub(),
        hash,
        len,
        prune: Cell::new((0, None)),
    })
}
'''
if old not in s:
    raise SystemExit('env_extend anchor not found')
p.write_text(s.replace(old, new, 1))
print('applied prune-env frame v3: eager dense frames for env depth <= 64')
