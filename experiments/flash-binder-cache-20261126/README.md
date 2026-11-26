# Open binder evaluation memo ablation

REJECTED for prefix performance promotion. The native census showed both
repeated environment projection and an existing value-interning layer. This
isolated, independently authored prototype tests whether Lambda/Pi values
can use that layer without another open-expression evaluation memo. Closed
and level-substituted caches, closure environment projection, interning and
all validation remain.

All 39 library tests, retained raw-export regressions and 16 source-record
controls pass. Four two-worker exact-prefix executions ACCEPT 25,131
declarations each; three exact loop controls pass. Software instructions rise
0.831% in aggregate, with losses in both alternating pairs. The prototype
fails the prospective 1% reduction gate, so complete-Mathlib and broad portable
qualification are not run. It changes no release and establishes no Arena score.

Apply prototype.patch to bc704eeb. The adjacent front-cache trial retains the
shared comparison harness and counter source. Every actual comparison has its
own immutable executable identities, input hash, controls and raw receipts.
