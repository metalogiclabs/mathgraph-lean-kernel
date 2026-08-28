from pathlib import Path
import sys

mode = sys.argv[1]
gates = {
    "rigid": "matches!(a, Value::Rigid { .. })",
    "atom": "matches!(a, Value::Sort { .. } | Value::NatLit { .. } | Value::StrLit { .. })",
    "closure": "matches!(a, Value::Unfold { .. } | Value::Lam { .. } | Value::Pi { .. })",
    "rigid_atom": "matches!(a, Value::Rigid { .. } | Value::Sort { .. } | Value::NatLit { .. } | Value::StrLit { .. })",
}
assert mode in gates, mode
gate = gates[mode]

p = Path("src/eval.rs")
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
new = f'''    #[inline]
    fn spine_snoc_hc(&mut self, prev: S<'t>, elim: Elim<'t>) -> S<'t> {{
        // MSI v21: preserve semantic identity at creation only for the selected
        // value family. V20 proved eager all-family canonicalization is too costly.
        let elim = match elim.view() {{
            ElimView::App(a) if !a.is_canonical() && ({gate}) => {{
                Elim::app(self.canonicalize_for_spine(a))
            }}
            _ => elim,
        }};
        let key = (prev as *const Spine<'t> as usize, elim_key(&elim));
        let arena = self.arena;
        match self.tc_cache.spine_hc.entry(key) {{
            Entry::Occupied(o) => *o.get(),
            Entry::Vacant(slot) => {{
                let s = value::spine_snoc(arena, prev, elim);
                let canon = prev.is_canonical()
                    && match elim.view() {{
                        ElimView::App(a) => a.is_canonical(),
                        ElimView::Proj {{ .. }} => true,
                    }};
                if canon {{
                    s.mark_canonical();
                }}
                *slot.insert(s)
            }}
        }}
    }}
'''
assert old in s, "spine_snoc_hc anchor not found"
p.write_text(s.replace(old, new))
print(f"applied MSI canon class v21 mode={mode}")
