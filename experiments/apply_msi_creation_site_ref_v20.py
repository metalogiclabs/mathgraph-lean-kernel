from pathlib import Path

p = Path('src/eval.rs')
s = p.read_text()
old = r'''    #[inline]
    fn spine_snoc_hc(&mut self, prev: S<'t>, elim: Elim<'t>) -> S<'t> {
        let key = (prev as *const Spine<'t> as usize, elim_key(&elim));
        let arena = self.arena;
        match self.tc_cache.spine_hc.entry(key) {
            Entry::Occupied(o) => *o.get(),
            Entry::Vacant(slot) => {
                let s = value::spine_snoc(arena, prev, elim);
                let canon = prev.is_canonical()
                    && match elim.view() {
                        ElimView::App(a) => a.is_canonical(),
                        ElimView::Proj { .. } => true,
                    };
                if canon {
                    s.mark_canonical();
                }
                *slot.insert(s)
            }
        }
    }
'''
new = r'''    #[inline]
    fn spine_snoc_hc(&mut self, prev: S<'t>, elim: Elim<'t>) -> S<'t> {
        // MSI v20: creation-site semantic identity.
        // For application eliminations, canonicalize the argument before the spine
        // hash-cons key is formed. This preserves already-known exact structural
        // sameness as O(1) pointer identity in the constructed spine. Thunks are
        // deliberately excluded: forcing remains demand-driven.
        let elim = match elim.view() {
            ElimView::App(a) if !a.is_canonical() && !matches!(a, Value::Thunk { .. }) => {
                Elim::app(self.canonicalize_for_spine(a))
            }
            _ => elim,
        };
        let key = (prev as *const Spine<'t> as usize, elim_key(&elim));
        let arena = self.arena;
        match self.tc_cache.spine_hc.entry(key) {
            Entry::Occupied(o) => *o.get(),
            Entry::Vacant(slot) => {
                let s = value::spine_snoc(arena, prev, elim);
                let canon = prev.is_canonical()
                    && match elim.view() {
                        ElimView::App(a) => a.is_canonical(),
                        ElimView::Proj { .. } => true,
                    };
                if canon {
                    s.mark_canonical();
                }
                *slot.insert(s)
            }
        }
    }
'''
assert old in s, 'spine_snoc_hc anchor not found'
s = s.replace(old, new)
p.write_text(s)
print('applied MSI creation-site ref v20')
