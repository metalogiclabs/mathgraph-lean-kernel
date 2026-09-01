from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
p = root / 'src/eval.rs'
s = p.read_text()
old = '''                let mut funs: Vec<ExprPtr<'t>> = Vec::with_capacity(count as usize);\n                funs.push(fun);\n                funs.push(f2);'''
new = '''                let mut funs: smallvec::SmallVec<[ExprPtr<'t>; 8]> = smallvec::SmallVec::new();\n                funs.push(fun);\n                funs.push(f2);'''
assert old in s, 'Step26 target not found'
p.write_text(s.replace(old, new, 1))
print('V4_STEP26_APP_FUN_SMALLVEC=YES')
