# Status

V1 is live on branch `developmental-conv-policy-v1-clean`.

Implemented:

- bounded generic policy language;
- lexicographic semantic/cost/MDL selection;
- structural feature whitelist that excludes benchmark identity;
- JSONL trace contract and JSON schema;
- synthetic nontrivial-policy self-test;
- frozen Arena-native success/failure gate;
- GitHub Actions compiler self-test;
- observational-only `conv.rs` trace injector behind `MATHGRAPH_CONV_TRACE`;
- structural trace extractor and census summary;
- repository-static Arena-native semantic/trace workflow.

The injector modifies only the CI working tree. It derives records from values the frozen baseline has already computed and performs no additional unfold/evaluation probes, so tracing does not intentionally perturb the conversion schedule.

Not yet implemented:

- counterfactual action replay for real conversion decisions;
- full generated Arena discovery/sealed trace collection;
- generated Rust policy emission;
- full Arena semantic and performance ablation gate.

Current deciding sequence:

1. trace smoke gate must compile and preserve tests;
2. static Arena census must preserve accept/reject outcomes and produce real structural decision records;
3. only then add counterfactual replay over the observed states;
4. fit on a frozen discovery set and decide on a sealed set;
5. retain a generated policy only if the preregistered gate passes.

Do not add another hand-written conversion heuristic before the real trace census identifies the next consequential separator.
