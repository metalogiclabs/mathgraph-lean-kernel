# Aeneas production-Rust extraction spike v1

## Objective

Test whether the pinned production Rust checker can be carried through Charon -> Aeneas -> Lean without changing checker semantics, starting from the exact A4 continuation source.

## Frozen source

- repository: metalogiclabs/mathgraph-lean-kernel
- base commit: 20a7a9fc4e3cea4f1b4cb8e04aecff4214533c27
- branch: experiment/aeneas-production-rust-spike-v1
- production target: src/relevance.rs
- first semantic primitives:
  - Sig::arg_is_ignorable
  - Sig::result_is_not_proof

No production Rust source is modified by this spike.

## Boundary

1. Run the existing Rust test suite on the frozen source.
2. Run Charon on the production crate with the Aeneas preset and emit LLBC.
3. Confirm the production relevance methods are present in the extracted representation/log.
4. Feed the generated LLBC to Aeneas's Lean backend.
5. Preserve all logs and generated files as an Actions artifact.

## Verdicts

- CHRON_EXTRACTION_FAILED: Charon cannot extract the pinned production crate.
- TARGET_NOT_REACHED: Charon succeeds but the selected production methods are not present/reachable in the emitted representation.
- AENEAS_TRANSLATION_FAILED: Charon succeeds and reaches the production target, but Aeneas cannot translate the resulting LLBC to Lean.
- AENEAS_TRANSLATED: generated Lean exists. This is only an extraction/translation result, not yet a semantic correspondence theorem.

## Non-claims

A green extraction does not establish Rust <-> Lean semantic equivalence, checker soundness, or correctness of the relevance optimization. Those require a subsequent theorem against the existing formal semantics.
