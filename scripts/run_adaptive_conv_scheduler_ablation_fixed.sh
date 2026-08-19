#!/usr/bin/env bash
set -euxo pipefail
cp scripts/run_adaptive_conv_scheduler_ablation.sh /tmp/run_adaptive_conv_scheduler_ablation_fixed.sh
# GNU time writes a diagnostic line for an expected non-zero checker exit. The two
# refutation benchmarks correctly exit 1, so keep only the numeric timing line.
# This wrapper is intentionally a separate file so a synchronization commit retriggers
# the PR workflow with the corrected parser while preserving the original failed harness.
sed -i "s#/usr/bin/time -f '%e'#/usr/bin/time -q -f '%e'#g" /tmp/run_adaptive_conv_scheduler_ablation_fixed.sh
sed -i 's#; cat /tmp/time.txt)#; tail -n 1 /tmp/time.txt)#g' /tmp/run_adaptive_conv_scheduler_ablation_fixed.sh
bash /tmp/run_adaptive_conv_scheduler_ablation_fixed.sh
