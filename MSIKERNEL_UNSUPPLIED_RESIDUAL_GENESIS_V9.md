# MSI-kernel V9: unsupplied residual genesis

Goal: close the remaining gap after Developmental Hypergraph V8. V8 established exact-semantic, cross-corpus path dependence and residual rescue, but the four portal transformations were pre-enumerated. V9 removes portal labels from the discovery step.

Protocol:
1. Freeze the post-G2 checker state.
2. Inspect executable Rust only for repeated behavioural demand patterns; do not consult V8 portal names during discovery.
3. Identify the strongest repeated producer/consumer residual in the source.
4. Synthesize a minimal executable structural shortcut from that local pattern.
5. Build it.
6. Require byte-identical checker outputs on frozen Std and Cedar prefixes.
7. Require strict Callgrind improvement on both corpora.
8. Only after the gate passes, compare the generated transformation post hoc with previously known portal families.

Success criterion:

`PORTAL_LABELS_USED=0` and `SYNTHESIS_EDITS>0`, followed by exact semantic equality and negative instruction deltas on both Std and Cedar.

A discovery-only annotation is not success. The generated candidate must change executable code and pass the verifier/economic gates.
