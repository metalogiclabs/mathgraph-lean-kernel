# Worker-count experiment on unchanged Flash

The revised core retains values across declaration sessions. Spreading
neighboring declarations over more workers can repeat work in separate
caches. The Arena ranks by total hardware instruction count, not wall time,
so the best worker count requires a cost measurement.

The calibrated fixed-prefix experiment intentionally compares **the same
executable** with distinct `--threads 1`, `--threads 2`, and `--threads 4`
arguments. It is not a comparison of allegedly different source builds.
All six executions ACCEPT the exact 25,131 declarations. Three analytical
loops match exactly, and separate one/two/four-worker calibration programs
show that every worker's loop enters the total count; library and thread
startup work remain within the declared 2% bound above the known loop body.

On two alternating prefix rounds, one worker uses 4.540% fewer estimated
application basic-block instructions than two; four use 2.794% more than two.
Two-worker counts vary with scheduling. This is a CANDIDATE configuration
lead, not a full-Mathlib or official PMU result. Instrumentation can also
perturb scheduling, and libraries remain inside the accounting boundary.

The complete-input workflow rebuilds the unchanged qualified checker with
the ordinary native flags, requires its unit/source/portable controls,
compares two alternating native pairs, then counts one complete execution
with each of one and two workers. Complete input bytes/SHA, checker hash,
raw exit status and all 739,167 declarations are required in each arm.
This experiment does not change the submitted Arena worker count.


## Complete native outcome; instrumented native execution unresolved

[Run45731082375](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45731082375)
passed all39 library tests/eight retained raw exports,230 portable outcomes,
16 source controls and four complete Mathlib native ACCEPTs. Each native
execution checks all739,167 declarations with raw exit0. The actual binary
is identical in both configurations. Artifact15077182392 is independently
SHA-256/CRC verified; all563 entries were rehashed.

| Native median | One worker | Two workers |
| --- | ---: | ---: |
| Total CPU |127.075s|131.565s|
| Wall time |126.335s|71.550s|
| Peak RSS |4,727,656KiB|4,900,918KiB|

One worker uses **3.413% less total CPU** and3.535% less peak RSS, while
wall time rises76.569%. This is a real tradeoff, not a parallel speedup.
The first software-instrumented native execution ended with **SIGILL(-4)**,
without a final instruction count or complete ACCEPT. Its cause remains
UNKNOWN. All six calibration/worker-coverage controls had passed, and
all four native full executions succeeded. The workflow is red because
of this failed diagnostic; it is not a semantic checker rejection.

Preserve the failed process receipt. A narrow recovery reuses the exact
generic binary `09fe7ecf...bd5b` that previously completed the full software
counter run, after requiring its original archive SHA-256, CRC and actual
binary hash. It keeps all calibration controls, both full ACCEPT gates,
and the exact Mathlib hash; it changes no release or submitted descriptor.
The recovery measures the generic-build instruction boundary and does not
replace or relabel the native measurements above.


## Generic recovery completed

[Run45733992103](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45733992103)
passed on the exact previously frozen generic executable09fe7ecf…bd5b.
All739,167 declarations ACCEPT with both worker counts. Six exact-loop and
thread-coverage controls pass. One worker counts545,996,703,520 software
instructions; two count556,736,069,952: **1.929% fewer** with one worker.
This is one complete execution per configuration, with the same binary,
input, counter and host. It does not resolve the native SIGILL or establish
a native PMU score. The earlier4.540% prefix gain overestimates the complete
input effect; do not transport the prefix ratio into the leaderboard.

Artifact15079500277 matches SHA-256 `13f00a6dc756053f43e85170720990e0dc01dd5782df750cc43759071d245deb`
and CRC; all55 archive-entry hashes, the actual executable hash and raw
counts were independently recomputed. Completed evidence is under
`../flash-worker-counter-recovery-20261126/completed/`. The large native
wall-time tradeoff remains; no submitted worker setting changes here.
