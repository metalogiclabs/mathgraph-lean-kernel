# Domain Contract — MathGraph Lean Kernel / Lean Kernel Arena

**Status:** MDA domain contract v1  
**Repository:** metalogiclabs/mathgraph-lean-kernel  
**Starting present:** `d6a73279e6765e637f9741180cefbd7ef957d8e5` (`dulce-de-leche`)  
**Pinned Arena:** `ac1c13762de41b594fa24b90ede8cfd97ac6a765`  
**Frozen MDA kernel SHA-256:** `0fcf675ba073a61c7a3a406e9ac6153e8ead4d3ee41563ef8265c9641f20e90e`  
**Frozen MDA implementation-prompt SHA-256:** `36ddc368c36d41b4fd4bc2bc3b1f00ed5d517e2efb81f9139f2f11d4ec970da5`

This contract instantiates the Minimal Developmental Algorithm for development of a Lean 4 proof checker whose external evaluation is the Lean Kernel Arena. It deliberately separates semantic ground, measurement and preference.

## 1. Domain

- **Name:** MathGraph Lean Kernel / Lean Kernel Arena checker development
- **Current executable present:** the accepted MathGraph `dulce-de-leche` checker at the starting-present SHA above.
- **Language/runtime:** Rust 2021, Cargo locked dependencies, release build with fat LTO.
- **Arena build mode:** four-thread checker configuration and PGO trained on `init-prelude`, matching the pinned Arena checker definition.
- **Scientific objective:** improve the Arena-ranked checker while preserving or improving benchmark-relative soundness/completeness.

## 2. Encounter interface

One Arena encounter is an exported Lean environment/test in the Arena NDJSON format, processed under the checker configuration.

- **Input:** one Arena test export / declaration stream.
- **Output:** process outcome interpreted by Arena: accept (exit 0), reject (exit 1), decline (exit 2), or error (other).
- **Ordering:** declaration order inside an export is semantic input; test ordering is not semantic ground.
- **Process state:** each Arena test is treated as an independent encounter unless an experiment explicitly states otherwise.
- **Hidden state:** no hidden benchmark label may be exposed to candidate code.

Instrumentation, synthetic probes and ablations are developmental encounters, not replacements for Arena semantic ground.

## 3. Grounding consequence / verifier (`V0`)

### 3.1 Primary benchmark-relative ground

For the pinned Arena suite, the expected test outcome is the external semantic authority used for promotion:

- an `accept` test is correct when the checker accepts;
- a `reject` test is correct when the checker rejects;
- an `either` test does not contribute to soundness/completeness scoring;
- decline/error is recorded separately and must not be silently recoded as semantic correctness.

The candidate checker may not alter Arena test inputs, expected outcomes, scoring logic or the reference benchmark in order to pass.

### 3.2 Local independent replay

Repository unit tests and explicit soundness regressions are protected local authorities for the properties they actually test. They do not by themselves prove equivalence to Lean's official kernel on arbitrary unseen input.

### 3.3 Claim boundary

This ground establishes benchmark-relative correctness on tested cases. Passing the finite Arena suite is not a theorem that the checker is sound and complete for all Lean programs.

## 4. Measurement interface (`M_t`)

Measurements are descriptive and do not by themselves establish semantic truth.

Record, when available:

- retired instruction count;
- instruction-derived virtual CPU time;
- wall time;
- user CPU time;
- system CPU time;
- peak RSS;
- checker exit status;
- build/PGO cost;
- selected stress-test times (including `con-leche`).

Hosted GitHub runners do not currently provide a reliable retired-instruction counter for these experiments. Local wall time is therefore a screening measurement only, not sufficient evidence of an Arena-ranking performance win.

## 5. Protected consequences (`Q_t`)

At minimum, a retained candidate must preserve:

1. zero newly introduced wrongly accepted invalid proofs relative to the frozen present and pinned ground;
2. zero newly introduced wrongly rejected valid proofs relative to the frozen present and pinned ground;
3. repository source/unit/soundness regression tests;
4. successful handling of Mathlib if the frozen present handles Mathlib;
5. any explicit correctness/security invariant already encoded by the starting-present tests;
6. exact checker interface/exit semantics expected by Arena.

A performance measurement is protected only when explicitly declared as such. In particular, a con-leche wall-time threshold is **not** semantic ground and is not automatically a protected consequence.

## 6. Warrant model

This is a mixed authority domain:

- **Arena suite:** finite benchmark-relative expected outcomes.
- **Repository tests:** finite regression evidence.
- **Formal/source reasoning:** may justify local implementation invariants but is not substituted for Arena replay.
- **Performance measurements:** empirical and noisy; repeated local timing does not become a semantic proof.
- **Instruction count:** authoritative for Arena's Mathlib performance ordering when obtained from the Arena measurement environment.

Non-observation is not impossibility. A candidate not failing the current suite remains only suite-qualified.

## 7. Developmental preorder / economy (`<=_t`)

Ground and warrant are applied before preference.

For candidates evaluated under the same Arena round, use the Arena scoring order lexicographically:

1. number of wrongly accepted invalid proofs;
2. number of wrongly rejected valid proofs;
3. Mathlib check time as defined by Arena (instruction count converted at the fixed instruction rate; a checker that cannot handle Mathlib ranks below one that can);
4. number of declined/crashed tests.

Only after these official dimensions are tied may auxiliary considerations such as peak memory, engineering complexity, maintenance burden or broader stress-test latency be used as secondary preference.

Thus:

```text
GROUND / WARRANT
    before
OFFICIAL ARENA SCORE
    before
AUXILIARY ENGINEERING PREFERENCE
```

Wall-time changes on hosted runners are proposal evidence only until the official instruction-based performance dimension is measured.

## 8. Starting continuation language

The initial MDA boot substrate may propose changes to:

- Rust checker source;
- representations and data structures;
- cache contents/policies;
- evaluation and conversion algorithms;
- environment representations/projection;
- search/unfolding order;
- retained metadata;
- PGO-compatible implementation structure;
- instrumentation and developmental experiment code;
- candidate probe/test generators, provided their outputs remain externally checked.

The continuation language is a boot substrate, not a permanent ontology. If it is itself certified inadequate, it may be expanded under the same MDA rule.

## 9. Probe / intervention interface

Authorized developmental probes include:

- controlled source ablations;
- joint/configuration ablations;
- pinned Arena accept/reject cases;
- Arena perf/stress cases;
- generated adversarial cases whose expected outcome is independently established;
- cache/path instrumentation;
- repeated timing measurements;
- differential comparison against a separately grounded checker where the comparison's authority is explicit.

Probe selection should discriminate surviving lawful alternatives, not merely maximize coverage.

## 10. Forbidden changes

A candidate may not, for the purpose of claiming improvement:

- alter pinned Arena expected outcomes;
- alter Arena scoring order;
- alter benchmark input after hidden/evaluation evidence is exposed;
- redefine accept/reject semantics;
- self-certify a changed semantic criterion;
- remove protected tests from replay and call the omission a pass;
- use test identity or hidden labels as a runtime branch;
- convert semantic failures into unreported success.

Changes to the checker submission/build definition are allowed only when explicitly included in the candidate present and evaluated under the same external ground.

## 11. Freeze boundary

Before a promotion/holdout run, freeze and record:

- MDA kernel hash;
- this domain contract hash/commit;
- starting/candidate present SHA;
- pinned Arena SHA;
- checker configuration;
- protected replay set;
- developmental preorder;
- candidate-generation/search procedure;
- probe generator;
- holdout set;
- exact source changes.

Harness-only repairs after freeze must be documented separately and must not alter the scientific candidate or its success criterion.

## 12. Direction choice

This is a mature engineered system, so **SOLVENT is the default first developmental direction**. This is a heuristic justified by the domain, not a constitutional law.

The untouched `d6a73279...` present remains the control.

SOLVENT must search lawful **configurations**, not infer global dispensability from single-component ablations. Historical V113–V121 results may seed provenance and candidate partitioning, but they do not by themselves authorize retention or contraction.

GENESIS should later be run from a deliberately reduced but lawful seed and compared against SOLVENT endpoints.

## 13. Promotion rule

A candidate is retained only after:

- protected semantic replay passes;
- its Arena score tuple is measured or, during screening, there is a clearly labelled proxy result;
- any claimed performance win is confirmed on the authoritative Arena performance measure before release;
- provenance, dependencies, contextual necessity and revocation conditions are recorded.

Exploration is not inheritance.
