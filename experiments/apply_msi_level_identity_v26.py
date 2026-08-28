from pathlib import Path
import sys

mode = sys.argv[1]
assert mode in {'simp_once','simp_ptr'}
p = Path('src/level.rs')
s = p.read_text()
old = r'''    pub fn eq_antisymm(&mut self, l: LevelPtr<'t>, r: LevelPtr<'t>) -> bool {
        l == r || (self.leq(l, r) && self.leq(r, l))
    }
'''
if mode == 'simp_once':
    new = r'''    pub fn eq_antisymm(&mut self, l: LevelPtr<'t>, r: LevelPtr<'t>) -> bool {
        if l == r {
            return true;
        }
        // MSI v26: simplify each side once, then reuse that sufficient
        // interface for both antisymmetry directions.
        let l = self.simplify(l);
        let r = self.simplify(r);
        self.leq_core(l, r, 0) && self.leq_core(r, l, 0)
    }
'''
else:
    new = r'''    pub fn eq_antisymm(&mut self, l: LevelPtr<'t>, r: LevelPtr<'t>) -> bool {
        if l == r {
            return true;
        }
        // MSI v26: simplify once, consume exact identity immediately,
        // and only traverse the antisymmetry relation if identity remains unresolved.
        let l = self.simplify(l);
        let r = self.simplify(r);
        l == r || (self.leq_core(l, r, 0) && self.leq_core(r, l, 0))
    }
'''
assert old in s, 'eq_antisymm anchor not found'
p.write_text(s.replace(old,new))
print(f'applied MSI level identity v26 mode={mode}')
