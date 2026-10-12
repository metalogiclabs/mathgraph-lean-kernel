#!/usr/bin/env bash
set -euxo pipefail

# v33 is a strict ablation of v32. Keep the dependency split, remove the
# binder-domain thunk: evaluate the binder domain eagerly under its own
# minimal environment. This isolates thunk tax from capture-splitting tax.

git show origin/experiment/split-lambda-capture-v32:experiments/run_split_lambda_capture_v32.sh > /tmp/v33-derived.sh
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/v33-derived.sh')
s=p.read_text()
s=s.replace('v32','v33').replace('V32','V33')
s=s.replace(
"""                let bt_env = self.key_env(env, binder_type);\n                let bt = value::mk_thunk(self.arena, bt_env, binder_type);""",
"""                let bt_env = self.key_env(env, binder_type);\n                let bt = self.eval(depth, bt_env, binder_type);""",1)
s=s.replace(
"""                let d = self.force_thunk(depth, binder_type);\n                self.tc_cache.lam_domain_cache.insert(addr, d);\n                d""",
"""                let d = *binder_type;\n                self.tc_cache.lam_domain_cache.insert(addr, d);\n                d""",1)
s=s.replace(
'DECISION=V33_KILL_SPLIT_CAPTURE__THUNK_OR_CAPTURE_TAX_EXCEEDS_DELETION',
'DECISION=V33_KILL_EAGER_SPLIT_CAPTURE__CAPTURE_OR_EAGER_EVAL_TAX_EXCEEDS_DELETION')
s=s.replace(
'DECISION=V33_ADVANCE_SPLIT_CAPTURE_TO_FULL_MATHLIB_PGO',
'DECISION=V33_ADVANCE_EAGER_SPLIT_CAPTURE_TO_FULL_MATHLIB_PGO')
s=s.replace(
'DECISION=V33_WEAK_POSITIVE__RETAIN_AND_MEASURE_MATHLIB_EXPOSURE',
'DECISION=V33_WEAK_POSITIVE_EAGER_SPLIT__RETAIN_AND_MEASURE_MATHLIB_EXPOSURE')
# Fail closed if the intended ablation did not attach.
assert 'let bt = self.eval(depth, bt_env, binder_type);' in s
assert 'let d = *binder_type;' in s
assert 'mk_thunk(self.arena, bt_env, binder_type)' not in s
p.write_text(s)
PY
bash /tmp/v33-derived.sh
