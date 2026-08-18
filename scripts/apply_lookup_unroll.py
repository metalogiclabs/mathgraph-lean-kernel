from pathlib import Path
import sys

root = Path(sys.argv[1])
_legacy_factor = int(sys.argv[2])

p = root / "src/infer.rs"
s = p.read_text()
old = """        let key = (self.key_env(env, e) as *const value::Env<'t> as usize, e);"""
new = """        let key_env = self.key_env(env, e);
        let key = (key_env as *const value::Env<'t> as usize, e);"""
assert s.count(old) == 1
s = s.replace(old, new, 1)
old2 = """                let clo = Closure::mk_infer(self.key_env(env, e), ctx, body);"""
new2 = """                let clo = Closure::mk_infer(key_env, ctx, body);"""
assert s.count(old2) == 1
s = s.replace(old2, new2, 1)
p.write_text(s)
