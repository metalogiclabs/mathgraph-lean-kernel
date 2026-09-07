# Developmental selector V1

This is a bounded experiment-selection assay, distinct from the Lean checker and from the conversion-policy compiler. It uses source-grounded historical observations to freeze a minimal policy, then tests the policy on later real episodes without refitting. Missing counterfactual outcomes remain UNKNOWN. A replay match is not a measured wall-time improvement or proof of general self-development.

The current frozen decision is to repair the v88 corpus-path mismatch before attempting another Rust optimization. No checker change is promoted. The original failed run is 34162953473; its preflight and PGO builds passed, but no replay or timing completed. The selected repair changes only the measurement input path from std.ndjson to init-prelude.ndjson, preserving the output label and all timing/semantic checks. The existing two missing negative fixtures remain a separate qualification blocker.

The full local evidence bundle and executable controller are retained as a separate artifact. This directory is not a claim that the prior synthetic developmental-controller gauntlet already proved live Arena self-improvement.