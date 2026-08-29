# Developmental Conversion Policy V1

This experiment turns Lean conversion scheduling into the developmental object.

Goal: replace hand-written benchmark-specific conversion heuristics with a small generated policy selected only by protected consequences.

The controller treats each conversion decision as a state `sigma`, chooses among generic actions such as compare-arguments, unfold-left, unfold-right, unfold-both, and memo/structural fallbacks, and searches for the minimum-description-length policy that preserves semantic correctness while improving protected Arena cost.

Scientific gate:

1. Freeze the current MathGraph checker as K0.
2. Collect conversion decision records from Arena workloads without benchmark names in the records.
3. Split workloads into discovery and sealed evaluation sets.
4. Generate bounded decision-tree policies over generic structural predicates only.
5. Require zero accept/reject regressions on protected tests.
6. Require a strict aggregate cost improvement on sealed evaluation.
7. Require at least one selected separator not equivalent to the existing hand-coded short-asymmetric-spine rule.
8. Ablate the generated policy and verify the gain disappears.

The intended loop is:

`conversion residual -> generated separator -> minimal policy refinement -> full semantic gate -> retain or discard -> next residual`

This directory contains the first bounded policy compiler and trace schema. Core-kernel instrumentation is intentionally kept behind an environment flag so the baseline checker remains unchanged when the experiment is disabled.
