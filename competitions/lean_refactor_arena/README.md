# Lean Refactor Arena — MathGraph Track 1

This directory is the isolated MathGraph harness for the VeriCodeGen / Lean Refactor Arena.

Competition target:
- Track 1: closed-source LLM harness
- hard budget: <= US$3 API spend per problem
- objectives: proof-source size, elaboration efficiency, and zero-shot version transfer
- warm-up: public development subset through 2026-09-30
- full benchmark: 2026-11-01
- final submission: 2026-11-08

The first gate is intentionally model-free. It proves that the local scoring/verification loop itself is sound before any refactoring intelligence is admitted.

## Developmental contract

For each problem:

1. Freeze the reference theorem and its environment.
2. Verify the reference.
3. Propose a candidate without changing the theorem statement.
4. Verify the candidate with Lean.
5. Measure only verified candidates.
6. Retain a candidate only when it strictly improves at least one measured objective without losing already-certified properties.
7. Replay retained candidates across configured toolchains.
8. Record every candidate, failure, retained change, and charged model cost.

No candidate can improve its score by failing verification.

## Smoke gate

```bash
python3 competitions/lean_refactor_arena/runner.py \
  --manifest competitions/lean_refactor_arena/fixtures/smoke/manifest.json \
  --out /tmp/lean-refactor-smoke.json
```

The included smoke problem has a deliberately long valid reference proof and a shorter valid candidate with the identical theorem declaration. CI installs Lean 4.24.0 and verifies both.

## Warm-up ingestion

The organizer-facing benchmark adapter will live under `warmup/`. Keep organizer data and submission formats separate from the evaluator core: the evaluator accepts a manifest of reference/candidate Lean files, so the public warm-up export can be dropped in without rewriting the loop.

The local token count in `runner.py` is only a deterministic development proxy. Official competition scoring remains authoritative.
