from pathlib import Path
import sys

root = Path(sys.argv[1])
arm = sys.argv[2]
p = root / 'src' / 'eval.rs'
s = p.read_text()

# V6 is deliberately a narrow producer/consumer fusion experiment.
# We avoid memoizing key_env and instead bypass repeated key_env construction
# when the consumer can directly use the producer's already-pruned env.
# The exact splice points are guarded so a source drift fails loudly.
needle = 'let key_env = self.key_env(env, e);'
if needle not in s:
    raise SystemExit('V6 splice point not found: key_env construction')

if arm == 'ablate':
    repl = '''let key_env = self.key_env(env, e);\n        // V6 ablation: pay a matched branch/check cost but preserve baseline consumer.\n        let _v6_fusion_probe = key_env.len();'''
elif arm == 'fusion':
    repl = '''// V6 fusion: if the incoming environment is already exactly the future-relative\n        // projection required by this expression, consume it directly instead of rebuilding.\n        let key_env = {\n            let projected = self.key_env(env, e);\n            if projected.len() == env.len() { env.clone() } else { projected }\n        };'''
else:
    raise SystemExit(f'unknown arm: {arm}')

s = s.replace(needle, repl, 1)
p.write_text(s)
