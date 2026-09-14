# Lean Refactor Arena — MathGraph Track 1

This directory is the isolated MathGraph harness for the VeriCodeGen / Lean Refactor Arena.

Competition target:
- Track 1: closed-source LLM harness
- hard budget: <= US$3 API spend per problem
- objectives: proof-source size, elaboration efficiency, and zero-shot version transfer
- warm-up: public development subset through 2026-09-30
- full benchmark: 2026-11-01
- final submission: 2026-11-08

The first gates are intentionally model-free. The verifier/evaluator substrate must earn trust before any paid refactoring intelligence is admitted.

## Organizer compatibility

The public organizer implementation is `delta-lab-ai/lean-refactor`. Its Arena path consumes a single JSONL file whose theorem records use:

- `name`
- `src`
- `path`
- `signature`
- `contexts`
- `proof_length`
- `header`

The organizer's bundled Mathlib snapshot is `mikeljl/mathlib4@f198c5fbaae84e872cb341731527553fc9c99f2a`, whose `lean-toolchain` is `leanprover/lean4:v4.24.0`.

`official_jsonl.py` validates the required input surface before a run starts. The official Arena score remains authoritative; local metrics are diagnostics and search signals only.

## Developmental contract

For each problem:

1. Freeze the reference theorem and environment.
2. Verify the reference.
3. Distinguish failed search from certified inadequacy.
4. Propose the smallest available change without altering the theorem statement.
5. Verify the candidate with Lean.
6. Measure only verified candidates.
7. Retain a candidate only when it strictly improves an objective without losing protected properties.
8. Replay retained candidates across configured toolchains.
9. Ablate or delete retained machinery periodically.
10. Record every candidate, failure, retained change, and charged model cost.

No candidate can improve its score by failing verification.

## First search: deletion only

`ddmin.py` is the first acquisition operator. It is deliberately weaker than a Lean refactoring system: it may only delete contiguous spans of tokens already present in the current proof.

It contains no tactic names, lemma names, strategy database, or hand-written proof transformations. For every proposed deletion:

```
current proof -> delete span -> Lean
                         |-> reject: restore
                         \-> accept: retain smaller present
```

The search tries the largest deletions first and restarts after every verified gain. This gives us a clean baseline for how far consequence alone can contract a proof before any generative model is allowed to add structure.

## Track-1 cost gate

`budget_ledger.py` is append-only and refuses a charge that would take any problem above US$3.00. CI proves the refusal path, not only the success path.

Paid model calls should be charged before their outputs are eligible for retention. A later run must therefore be reproducible from the ledger plus the retained proposal trace.

## CI smoke gate

The workflow `.github/workflows/lean-refactor-arena-track1.yml` currently proves:

- organizer-schema JSONL is accepted;
- reference and fixed candidate preserve the declaration and both verify;
- a shorter fixed candidate is measured as a contraction;
- the Track-1 ledger admits spend below the cap and refuses an overrun;
- deletion-only search discovers a verified contraction from the longer proof;
- the discovered proof replays on Lean 4.23.0 and the organizer-matching Lean 4.24.0;
- evidence is uploaded as a run artifact.

## Warm-up

Download the public Arena JSONL from the organizer's Lean Refactor Arena space and place it outside the immutable evaluator core. Validate it first:

```bash
python3 competitions/lean_refactor_arena/official_jsonl.py \
  /path/to/lean-refactor-arena.jsonl \
  --summary-out /tmp/arena-summary.json
```

The next layer is a benchmark runner that materializes each organizer record into the pinned Mathlib workspace, applies model-free contraction first, then opens paid proposal channels only at the residual boundary. All paid calls remain under the per-problem hard ledger.
