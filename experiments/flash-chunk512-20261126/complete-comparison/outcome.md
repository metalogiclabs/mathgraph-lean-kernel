# Complete comparison: retain qualification, reject the priority gate

The one-line scheduling candidate passes all 240 distinct original prescribed
inputs on frozen generic executable 878d871f. It does **not** pass the
predeclared performance priority gate of at least 1% fewer complete-input
software instructions. No source or worker-count change is promoted to PR398.

| Complete Mathlib measurement | Qualified 64-declaration batches | Candidate 512-declaration batches |
| --- | ---: | ---: |
| Two-worker software instructions | 557,278,137,483 | 552,616,945,844 |
| Native median total CPU | 136.230 s | 135.220 s |
| Native median wall time | 74.030 s | 73.380 s |
| Native median peak RSS | 4,897,802 KiB | 4,842,072 KiB |

The software reduction is **0.836421%**, from one complete execution per arm.
Both ACCEPT all 739,167 original declarations, with three exact loop controls
and a separate two-worker coverage control. The earlier 2.330% prefix estimate
overstates the observed whole-input effect. This is a bounded measurement,
not a proof of zero benefit or a universal rejection of larger batches.

The separate matched native builds complete four ACCEPTing executions in
two alternating pairs. Median CPU falls 0.741%, but paired CPU changes have
opposite directions (+0.317%, -1.745%). Wall time falls 0.878% and RSS 1.138%
in these observations. Native costs and generic software counts are separate
measurements and their percentages cannot be combined.

[Run45737482656](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45737482656)
and artifact15082331579 succeeded. The archive SHA-256 is
`6b665252aa5e21bcc492ca522430c140713583c4a378f2fc99a331a00d005f2d`.
Independent verification checks CRC, all 589 entry hashes, actual generic
and native executable bytes, original input identity, raw outcomes/count
markers, calibration and paired native timing receipts. The 579 UTF-8 text
receipts are packed by their original archive paths in `raw-text-receipts.json`;
encoding each value as UTF-8 reproduces its exact original bytes and digest.
Binaries remain in the source archive and are identified in the inventory.

The original counter was used throughout. The experimental TLS counter,
its failed agreement gate and subsequent variation observations are excluded.
Native compatibility of the other nine large exports, an official hardware
score and a new Arena rank remain outside this warrant. Keep the clean
source4816054e and this outcome for reuse; do not rerun until a new hypothesis
or measurement question justifies the cost.
