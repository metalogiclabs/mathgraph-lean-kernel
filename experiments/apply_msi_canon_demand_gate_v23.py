from pathlib import Path
import sys

mode = sys.argv[1]
assert mode in {'no_rigid','no_unfold','no_both','if_prev'}

p = Path('src/eval.rs')
s = p.read_text()

rigid_old = r'''                let a = self.canonicalize_for_spine(a);
                let new_spine = self.spine_snoc_hc(spine, Elim::app(a));
                self.mk_rigid_hc(head_copy, new_spine)
'''
unfold_old = r'''                let a = self.canonicalize_for_spine(a);
                let new_spine = self.spine_snoc_hc(spine, Elim::app(a));
                self.mk_unfold_hc(head.name, head.levels, new_spine, head_value)
'''
assert s.count(rigid_old) == 1, f'rigid anchor count={s.count(rigid_old)}'
assert s.count(unfold_old) == 1, f'unfold anchor count={s.count(unfold_old)}'

if mode in {'no_rigid','no_both'}:
    rigid_new = r'''                let new_spine = self.spine_snoc_hc(spine, Elim::app(a));
                self.mk_rigid_hc(head_copy, new_spine)
'''
elif mode == 'if_prev':
    rigid_new = r'''                let a = if spine.is_canonical() { self.canonicalize_for_spine(a) } else { a };
                let new_spine = self.spine_snoc_hc(spine, Elim::app(a));
                self.mk_rigid_hc(head_copy, new_spine)
'''
else:
    rigid_new = rigid_old

if mode in {'no_unfold','no_both'}:
    unfold_new = r'''                let new_spine = self.spine_snoc_hc(spine, Elim::app(a));
                self.mk_unfold_hc(head.name, head.levels, new_spine, head_value)
'''
elif mode == 'if_prev':
    unfold_new = r'''                let a = if spine.is_canonical() { self.canonicalize_for_spine(a) } else { a };
                let new_spine = self.spine_snoc_hc(spine, Elim::app(a));
                self.mk_unfold_hc(head.name, head.levels, new_spine, head_value)
'''
else:
    unfold_new = unfold_old

s = s.replace(rigid_old, rigid_new).replace(unfold_old, unfold_new)
p.write_text(s)
print(f'applied MSI canon demand gate v23 mode={mode}')
