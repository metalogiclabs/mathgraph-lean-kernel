# LEAN PERF COUNTER PROBE V1C — prospective diagnostic precommit

Status: **FROZEN BEFORE EXECUTION**

## Parent context

Parent measurement-recovery run:

- run: 35533345013
- job: 106137872850
- scientific result: PASS_SELECTED_ACTION_MEASUREMENT_RECOVERY_V1B

V1B did **not** validly diagnose hardware-counter availability because it resolved \`perf\` from the repository root:

\[
\texttt{nix develop -c sh -c 'command -v perf'}
\]

where no \`flake.nix\` existed. That caused \`PERF\` to be empty and produced exit code 127 before \`perf\` executed.

## Single hypothesis

The root cause of the V1B probe failure is incorrect Nix environment resolution caused by the working directory, not necessarily hardware-counter denial.

The minimal test is therefore:

1. clone the pinned Lean Kernel Arena;
2. check out commit \`510fbfead6f02bed1a0179d01729a6ddf5bfd06d\`;
3. \`cd /tmp/arena\`;
4. resolve \`perf\` from that Arena Nix environment;
5. run explicit counter probes with stdout, stderr, and return codes visible.

No checker build, PGO build, Mathlib benchmark, candidate mutation, or performance comparison is allowed in this diagnostic.

## Frozen probes

Record:

- resolved \`perf\` path;
- \`perf --version\`;
- \`/proc/sys/kernel/perf_event_paranoid\` when readable;
- \`perf stat -e instructions true\`;
- \`perf stat -e cycles true\`;
- \`perf stat -e task-clock true\`.

The **headline question** is the \`instructions\` event.

The other two probes classify whether failure is:
- general perf execution failure;
- hardware-event restriction;
- event-specific restriction.

## Frozen classifications

### COUNTER_AVAILABLE

\`perf stat -e instructions true\` returns 0 and reports a numeric instruction count.

### HARDWARE_COUNTER_DENIED

\`perf\` resolves and executes, but the \`instructions\` probe fails with a permission / unsupported / not-counted diagnostic.

### PERF_EXECUTION_FAILURE

\`perf\` resolves, but execution fails for another reason.

### PERF_RESOLUTION_FAILURE

\`perf\` still cannot be resolved from the pinned Arena environment.

## Gates

PC1. Pinned Arena commit is exact.

PC2. Probe runs from \`/tmp/arena\`.

PC3. \`perf\` resolution result is explicitly recorded.

PC4. \`perf --version\` is recorded if resolution succeeds.

PC5. \`perf_event_paranoid\` is recorded when readable.

PC6. Instructions probe stdout, stderr, and return code are all recorded.

PC7. Cycles probe stdout, stderr, and return code are all recorded.

PC8. Task-clock probe stdout, stderr, and return code are all recorded.

PC9. Classification is one of the four frozen categories.

PC10. No long benchmark, checker build, PGO build, or candidate execution occurs.

## Claim boundary

This experiment diagnoses only counter availability on this GitHub-hosted runner image and pinned Arena environment. It does not measure MathGraph performance.

The target is:

\[
\boxed{\textbf{Did the prior probe fail because of our workflow, or because the runner cannot expose the hardware counter?}}
\]
