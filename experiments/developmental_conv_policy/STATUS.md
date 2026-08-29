# Status

V1 scaffold is live on branch `developmental-conv-policy-v1-clean`.

Implemented:

- bounded generic policy language;
- lexicographic semantic/cost/MDL selection;
- structural feature whitelist that excludes benchmark identity;
- JSONL trace contract and JSON schema;
- synthetic nontrivial-policy self-test;
- frozen Arena-native success/failure gate;
- GitHub Actions self-test workflow.

Not yet implemented:

- `conv.rs` env-flagged state instrumentation;
- counterfactual action replay for real conversion decisions;
- discovery/sealed Arena trace collection;
- generated Rust policy emission;
- full Arena semantic and performance ablation gate.

The next code change should be instrumentation only; do not add another hand-written conversion heuristic before the real trace census decides the next separator.
