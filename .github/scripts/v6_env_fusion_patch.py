from pathlib import Path
import sys

root = Path(sys.argv[1])
arm = sys.argv[2]
p = root / 'src' / 'eval.rs'
s = p.read_text()

# V6 boundary-validation run against the actual frozen-V2 consumer site.
# mk_thunk_hc computes the canonical key environment as `te` before using it
# in the thunk hash-cons key and thunk payload. Keep the hypothesis unchanged:
# test whether a full-mask environment can be consumed directly.
needle = '        let te = self.key_env(env, e);\n        let key = (te as *const value::Env<\'t> as usize, e);'
if needle not in s:
    raise SystemExit('V6 splice point not found: mk_thunk_hc key_env boundary')

if arm == 'ablate':
    repl = '''        let te = self.key_env(env, e);\n        // V6 ablation: matched cheap observation; preserve baseline consumer.\n        let _v6_fusion_probe = e.as_ref().fv_mask();\n        let key = (te as *const value::Env<'t> as usize, e);'''
elif arm == 'fusion':
    repl = '''        // V6 fusion: when the expression needs every represented slot, the\n        // producer environment is already the exact projection. Bypass key_env.\n        let mask = e.as_ref().fv_mask();\n        let te = match env {\n            value::Env::Framed { mask: env_mask, .. } if *env_mask & mask == *env_mask => env,\n            _ => self.key_env(env, e),\n        };\n        let key = (te as *const value::Env<'t> as usize, e);'''
else:
    raise SystemExit(f'unknown arm: {arm}')

s = s.replace(needle, repl, 1)
p.write_text(s)
