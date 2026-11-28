# Selective inferred-Pi interning

Pinned nano-lean source motivated separating ordinary Pi interning from the
construction of inferred function types. The native prefix census finds one
reuse in 311,862 inferred-Pi requests. The independently authored prototype
allocates only inference-closure Pi nodes without probing the general
interner; it retains their exact environment, typing context and domain.
Ordinary evaluation Pi values continue to be interned.

The full library suite passes 40 tests, including a dependent-codomain
characterization with positive and negative type comparisons, and 16 source
controls pass. Two alternating two-worker prefix pairs accept all 25,131
declarations; three exact loop controls pass. Software instructions fall
0.844% in aggregate, but the pairs save about 1.495% and 0.190%. This fails
the prospective gate of at least 1% in both pairs. It remains unpromoted;
whole-input, broad portable and Arena effects are UNKNOWN.

The census is observation-only and excluded from speed comparisons. Its
first attempted build used the wrong working directory and was discarded
before measurement. A subsequent correct-source compiler was SIGKILLed;
a repeat after freeing this task's reproducible build intermediates
completed. The SIGKILL cause remains UNKNOWN. Original build logs are
retained, and only the successful identified executable enters the census.

The source mechanism is informed by nano-lean 5cd4a25, especially
src/value_checker/intern.rs and infer.rs. No competitor implementation is
copied into this patch. Flash retains its credited sokonanoda lineage.
