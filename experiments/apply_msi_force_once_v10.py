from pathlib import Path
p=Path('src/conv.rs')
s=p.read_text()
old='''        let (t, t2) = (self.force_thunk(depth, x), self.force_thunk(depth, y));\n        if let Some(r) = self.conv_nat::<RIGID>(depth, t, t2) {\n'''
new='''        // x and y are already forced by unify() before reaching unify_no_cache().\n        // Carry that semantic fact forward instead of recomputing it.\n        let (t, t2) = (x, y);\n        if let Some(r) = self.conv_nat::<RIGID>(depth, t, t2) {\n'''
if old not in s:
    raise SystemExit('unify_no_cache force anchor missing')
s=s.replace(old,new,1)
p.write_text(s)
print('applied MSI force-once v10')
