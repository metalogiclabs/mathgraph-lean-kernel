from pathlib import Path

p = Path('src/eval.rs')
s = p.read_text()
needle = '''    #[inline(never)]
    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {
        let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];
'''
insert = '''    #[inline(never)]
    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {
        // Consequence-first specialization: a one-bit demand can retain at most one
        // value. Construct exactly the same canonical frame without entering the
        // generic 64-slot collector. All other demands use the original path.
        if mask.is_power_of_two() {
            let wanted = mask.trailing_zeros();
            let lsub = e.lsub();
            let mut slots_hash = lsub.map_or(0, |l| l as *const value::LevelSub<'t> as usize as u64);
            let mut cur = e;
            let mut consumed = 0u32;
            let mut selected: Option<V<'t>> = None;
            let mut out_mask = 0u64;
            loop {
                match cur {
                    value::Env::Nil { .. } => break,
                    value::Env::Cons { v, parent, .. } => {
                        if consumed == wanted {
                            selected = Some(*v);
                            out_mask = 1u64 << wanted;
                            break;
                        }
                        consumed += 1;
                        cur = parent;
                    }
                    value::Env::Framed { mask: fmask, slots, .. } => {
                        if wanted >= consumed {
                            let rel = wanted - consumed;
                            if rel < 64 && ((*fmask >> rel) & 1) != 0 {
                                let below = if rel == 0 { 0 } else { *fmask & ((1u64 << rel) - 1) };
                                selected = Some(slots[below.count_ones() as usize]);
                                out_mask = 1u64 << wanted;
                            }
                        }
                        break;
                    }
                }
            }
            let one: [V<'t>; 1];
            let slots: &[V<'t>] = if let Some(v) = selected {
                slots_hash = slots_hash
                    .wrapping_mul(0x9E3779B97F4A7C15)
                    .wrapping_add(v as *const Value<'t> as usize as u64);
                one = [v];
                &one
            } else {
                &[]
            };
            let hash = out_mask.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(slots_hash);
            let r = self.intern_frame(hash, out_mask, slots, lsub);
            self.tc_cache.prune_dm[slot] = (e as *const value::Env<'t> as usize, mask, Some(r));
            match e {
                value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } => prune.set((mask, Some(r))),
                value::Env::Nil { .. } => {}
            }
            return r;
        }

        let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];
'''
if needle not in s:
    raise SystemExit('target not found')
s = s.replace(needle, insert, 1)
p.write_text(s)
print('applied prune single-demand v7')
