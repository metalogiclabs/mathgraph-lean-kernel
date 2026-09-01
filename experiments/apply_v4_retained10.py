#!/usr/bin/env python3
"""Frozen V4 retained10 applicator.

Applies exactly the ten interventions retained by deterministic Arena ablation
through Step 27 to an exact 2de1895 source tree.
"""
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
here = Path(__file__).resolve().parent

def run(script, *args):
    subprocess.run([sys.executable, str(here / script), str(root), *args], check=True)

# Retained 1-6: app direct-Pi, direct-Sort, projection param direct-Pi,
# projection final-field direct-Pi, duplicate force_thunk removal,
# streaming spine probe.
run("apply_v4_retained6.py")

# Retained 7: WHNF admission threshold 2 -> 1.
eval_rs = root / "src/eval.rs"
s = eval_rs.read_text()
old = "WHNF_ADMIT_THRESHOLD: u8 = 2"
new = "WHNF_ADMIT_THRESHOLD: u8 = 1"
if old not in s:
    raise SystemExit("retained10 WHNF threshold anchor not found")
eval_rs.write_text(s.replace(old, new, 1))

# Retained 8: do not write cold-derived prune results into the one-entry local slot.
run("apply_v4_step21_prune_retention.py", "nocold")

# Retained 9: fused open-eval cache/environment-pruning dispatch.
run("apply_v4_step24_eval_open_cache_fusion.py")

# Retained 10: one-pass path when heterogeneity is known from the first two functions.
run("apply_v4_step27_immediate_hetero_app.py")

print("V4_RETAINED10_APPLIED=YES")
