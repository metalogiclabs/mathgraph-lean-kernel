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
