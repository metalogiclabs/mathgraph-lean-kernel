#!/usr/bin/env bash
set -euxo pipefail
cp scripts/run_adaptive_conv_scheduler_ablation.sh /tmp/run_adaptive_conv_scheduler_ablation_fixed.sh
# Preserve the frozen scheduler hypothesis. This wrapper fixes harness-only failures:
# expected non-zero checker exits no longer contaminate timing output, sub-10ms
# diagnostics with a rounded 0.00s baseline no longer crash the reporter, and the
# Arena full semantic gate uses build-test with no name (the supported all-tests form).
sed -i "s#/usr/bin/time -f '%e'#/usr/bin/time -q -f '%e'#g" /tmp/run_adaptive_conv_scheduler_ablation_fixed.sh
sed -i 's#; cat /tmp/time.txt)#; tail -n 1 /tmp/time.txt)#g' /tmp/run_adaptive_conv_scheduler_ablation_fixed.sh
python3 - <<'PY'
from pathlib import Path
p = Path('/tmp/run_adaptive_conv_scheduler_ablation_fixed.sh')
s = p.read_text()
old = "        print(f'  {arm:8s} {m:.6f}  ratio_vs_baseline={m/b:.6f} delta={(m/b-1)*100:+.3f}%')"
new = "        if b == 0:\n            print(f'  {arm:8s} {m:.6f}  ratio_vs_baseline=NA delta=NA')\n        else:\n            print(f'  {arm:8s} {m:.6f}  ratio_vs_baseline={m/b:.6f} delta={(m/b-1)*100:+.3f}%')"
if old not in s:
    raise SystemExit('zero-time reporter splice not found')
s = s.replace(old, new, 1)
old_gate = 'nix develop -c ./lka.py build-test --all'
new_gate = 'nix develop -c ./lka.py build-test'
if old_gate not in s:
    raise SystemExit('full semantic gate splice not found')
s = s.replace(old_gate, new_gate, 1)
p.write_text(s)
PY
bash /tmp/run_adaptive_conv_scheduler_ablation_fixed.sh
