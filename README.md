# MathGraph Lean Kernel

A high-performance experimental proof checker for Lean 4, developed by [Metalogic Labs](https://mathgraph.org/).

MathGraph builds on:
- [nanoda_lib](https://github.com/ammkrn/nanoda_lib)
- [sonanoda](https://github.com/datokrat/sonanoda)
- [still-nanoda](https://github.com/SchrodingerZhu/still-nanoda)
- [sokonanoda](https://github.com/intgrah/sokonanoda)

The checker is developed as a testing bed for high-performance Lean typechecking, soundness testing, differential testing, and checker validation. It is tested against the [Lean Kernel Arena](https://arena.lean-lang.org/), including its accept/reject corpus and large Lean environments such as mathlib.

The core conversion algorithm is closure-based, with additional implementation-level optimisations. MathGraph remains an experimental kernel implementation and is not a replacement for Lean's official kernel.
