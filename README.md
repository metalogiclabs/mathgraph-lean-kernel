# MathGraph Lean Kernel

A high-performance experimental proof checker for Lean 4, developed by [Metalogic Labs](https://mathgraph.org/).

MathGraph builds on:
- [nanoda_lib](https://github.com/ammkrn/nanoda_lib)
- [sonanoda](https://github.com/datokrat/sonanoda)
- [still-nanoda](https://github.com/SchrodingerZhu/still-nanoda)
- [sokonanoda](https://github.com/intgrah/sokonanoda)

The checker is used as a testing bed for kernel performance, soundness testing and differential testing. It is evaluated in the [Lean Kernel Arena](https://arena.lean-lang.org/), including accept/reject tests and large Lean environments such as mathlib.

The core conversion algorithm is closure-based, with additional implementation-level optimisations.

This remains an experimental kernel implementation and is not a replacement for Lean's official kernel.
