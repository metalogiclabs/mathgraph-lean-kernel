# Application skipping and checked-codomain reuse

This experiment compares independent skip and reuse changes against the
qualified Flash source, with a fourth arm enabling both changes. The 9 MiB
session budget and all existing source-record checks remain intact.

The skip arm avoids unused lambda-argument and let-value evaluation while
preserving binder positions. A direct erasing beta redex is handled before
the existing eager right-spine shortcut can force its argument. The reuse
arm carries an atomic, closed result type already established while checking
a lambda into its codomain closure. Open and dependent result types retain
the original inference path. No competitor implementation is copied.

All four local builds pass 44 library tests, retained export regressions and
16 source-record controls. Test-only counters verify demand scaling, repeated
codomain application, an InferOnly-to-Check upgrade, dependent bound types,
and local/global level identity across resets. Counters are absent from the
production executables. Pure evaluation microtests deliberately clear memos
after establishing validity; production measurements retain ordinary caches.

The prospective protocol, source identity and complete patch are retained.
The four-arm prefix screen measures the same generic executables with a
calibrated software instruction counter and without instrumentation for
CPU/RSS. A hosted matrix checks all 230 exact portable prescribed exports.
These experiments establish bounded claims only; full Mathlib, the other
large cases and independent Arena measurements are separate gates.

The baseline compiled-symbol profile is an exclusive instruction diagnostic
on the exact prefix. Inlined work belongs to its compiled symbol. Its buckets
do not identify how much of a function's work is avoidable.

Local broader-case process kills are preserved as UNKNOWN, including kills
of the unchanged baseline. They are not normalized into semantic rejections.
