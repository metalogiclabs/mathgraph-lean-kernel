# MathGraph Lean Kernel

A high-performance experimental proof checker for Lean 4, developed by [Metalogic Labs](https://mathgraph.org/).

MathGraph builds on:
- [nanoda_lib](https://github.com/ammkrn/nanoda_lib)
- [sonanoda](https://github.com/datokrat/sonanoda)
- [still-nanoda](https://github.com/SchrodingerZhu/still-nanoda)
- [sokonanoda](https://github.com/intgrah/sokonanoda)

The checker focuses on kernel performance, soundness testing, differential testing and validation against the [Lean Kernel Arena](https://arena.lean-lang.org/).

It is tested on the Arena accept/reject corpus and large Lean environments including mathlib. The implementation uses a closure-based conversion algorithm together with additional programming-level optimisations.

MathGraph remains an experimental kernel implementation and is not a replacement for Lean's official kernel.
