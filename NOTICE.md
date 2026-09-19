# NOTICE

This repository is an experimental derivative in the nanoda / still-nanoda / sokonanoda lineage.

## Upstream lineage

MathGraph's current kernel implementation is derived from work including:

- `nanoda_lib` by the nanoda contributors;
- `still-nanoda` by SchrodingerZhu and contributors;
- `sokonanoda` by Jeremy Chen (`intgrah`) and contributors.

The Lean Kernel Arena-facing MathGraph checker intentionally preserves the `sokonanoda` lineage in its description. Metalogic Labs does not claim authorship of upstream mechanisms merely because they are present in this fork.

The repository is distributed under the Apache License 2.0. Existing copyright, license, and attribution notices in upstream source history remain applicable.

## Metalogic Labs work

Metalogic Labs' work in this fork consists of experimental kernel changes, profiling infrastructure, qualification workflows, performance interventions, regression tests, evidence artifacts, and documentation developed on top of that upstream implementation.

For Arena releases, retained changes are intended to be documented with exact source revisions and their qualification evidence. Where an optimization is adapted from another project or contributor, that provenance should be recorded rather than relabeled.

## AI-assisted development

AI coding and analysis tools have been used extensively in the development process, including experiment generation, implementation assistance, test/workflow authoring, analysis, and documentation.

No model output is treated as verification authority. Public performance or semantic claims should be grounded in reproducible source revisions, executable tests, differential qualification, formal proof where available, or authoritative Arena measurements.

## Research claim boundary

MathGraph's current Arena checker is not presented as a formally verified Lean kernel. Separate work in the Lean community on formal specifications and verified checkers—including Metalean, Lean4Lean, con-leche, con-ron, and related projects—addresses different and complementary assurance boundaries.
