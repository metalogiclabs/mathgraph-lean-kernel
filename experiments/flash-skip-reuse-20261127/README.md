# Application skipping and checked-codomain reuse: results

The four-way experiment passes its bounded correctness checks, but none of
the candidate arms passes the prospective prefix instruction gate. No release
or Arena submission was changed.

| Arm | Prefix instruction change | Paired changes | Cost gate |
| --- | ---: | --- | --- |
| Skip unused evaluation | +0.634% | +0.871%, +0.395% | Failed |
| Reuse checked atomic closed codomains | -0.771% | -0.459%, -1.084% | Failed |
| Both | +0.098% | -0.182%, +0.379% | Failed |

Negative instruction changes are reductions. All four executables were built
from the same source patch with independent static feature gates; the control
has both features disabled. The 9 MiB session budget, imported-declaration
correspondence checks and original dependent-type fallback remain intact.

The gate was fixed before candidate observations: at least 1% reduction in
each alternating pair and aggregate, or twice the initial baseline-control
fractional range if larger. The baseline controls varied by 0.136%, so the
gate remained 1%. All sixteen measured executions accepted the exact
25,131-declaration prefix. Three exact loop calibrations passed. The same
frozen generic executables were used for software counts and uninstrumented
CPU/RSS; the short two-observation CPU timings are diagnostic only.

## Correctness and mechanism evidence

Every arm passes 44 library tests, retained source regressions and 16 raw
source-record controls. The [hosted qualification](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45881611501)
passes all 230 exact portable prescribed exports in every arm. All four ZIP
archives, checker executable hashes, source identities and corpus rows were
independently checked; all 2,092 ZIP entries passed CRC verification.

With payload size 128, the isolated unused-lambda and unused-let evaluation
controls fall from 133 evaluator requests to 2; the used-argument control
still performs 132. In the distinct-binding codomain-application control,
inference requests fall from 384 to zero. These are test-only event counts,
not instruction or time savings. The pure evaluation controls deliberately
clear memos after validation; end-to-end measurements retain ordinary caches.
Production executables contain no test counter instrumentation.

Controls reject an ill-typed unused argument even after InferOnly warmed its
cache, retain dependent/open codomain contexts, distinguish local/global
universe IDs after storage reset, and reject a shared expression under an
undeclared universe after a valid declaration warmed the same session.

The local transfer screen retains 180 correct outcomes and two SIGKILLs per
arm, including kills of the unchanged control. The hosted qualification
resolves corpus completeness for its builds; the local signal cause remains
UNKNOWN. Raw failed attempts and all scope controls remain in the archive.

## Interpretation

These implementations demonstrate the intended mechanisms without earning
promotion. Their complete Mathlib and remaining nine large-case effects are
UNKNOWN because all candidates failed the prefix gate. The experiment
rejects these implementations at this boundary, rather than establishing a
general limit on demand-directed evaluation or scoped reuse.

A separately [verified prior full-input profile](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45717337815)
of the original qualified executable attributes 9.596% of software-counted
instructions to prune_env_cold and 5.118% to intern_frame. The fresh prefix
profile puts the same two buckets at 9.774% and 5.443%. These are exclusive
compiled-symbol buckets, including inlined work; they do not establish the
fraction that can be removed. The next unresolved question is how much of
that environment work can be passed directly between inference and evaluation.

## Reproducibility

- [Decision and boundaries](decision.json)
- [Factorial results](factorial-summary.json)
- [Verified portable qualification](portable-summary.json)
- [Prospective protocol](protocol.json)
- [Exact source patch](prototype.patch)
- [Complete text evidence archive](evidence.tar.gz)

The evidence archive retains raw measurements, test logs, original failed
attempts, source/control identities, profile records and artifact receipts.
Compiled executable identities are retained; their original hosted archives
remain linked through the artifact records. Candidate results are not official
Arena scores. The full 6.3 GB input hash is runner evidence; that input was
not independently downloaded for the reused profile verification.
