# Measured Flash combination experiment

The selected source combines canonical inference-environment handoff,
`eval_node` inlining and a 36 MiB value-session budget. The existing four-times
retention formula is unchanged. Base source is `bc704eeb`; the source candidate
is `1a284c5f4466a4ade68f576bfe34ca1d90eaa9af`, src tree
`498d5312b2abb1a1a9fe93127c47a0ae48dc1009`.

## Exact-prefix results

| Source combination | Fewer software instructions vs released source |
| --- | ---: |
| Projection alone, new controlled-path rerun | 2.407% |
| Projection + evaluator inlining | 3.295% |
| Projection + inlining + 512 batches | 5.364% |
| Projection + inlining + 18 MiB | 6.991% |
| Projection + inlining + 36 MiB | 9.944% |
| Projection + inlining + 512 batches + 36 MiB | 11.331% |

Every row was measured directly. Percentages are not added. All builds use the
same absolute source/target directories and compiler flags; source/executable
hashes are frozen. Two alternating instruction pairs and four separate native
rounds per arm use the original 25,131-declaration prefix and calibrated client.
The prospective threshold, fixed from baseline/parent controls before candidate
measurement, is 2.092%. Larger batches add only 1.541% beyond the selected
three-change stack, so the smaller stack is retained. The 36 MiB variant clears
the threshold against 18 MiB. These are prefix results, not complete Mathlib.

Fresh Init-only PGO accepts 59,626 declarations in each training replay and
passes profile hash validation. Its extra 0.530% instruction reduction fails
the separate 1% priority gate. The matched ordinary explicit-target rebuild
saves 9.705% versus released source; that observation is retained separately.
Missing profile coverage warnings remain distinct from hash mismatches.

A final same-executable argv study measures 10.308% fewer instructions with
two workers and 15.407% with one worker, both versus the released two-worker
checker. One worker adds a measured 5.685% reduction beyond the same stack with
two workers, while elapsed time grows 57.730% versus the released checker
(56.180% versus the two-worker stack). This is a ranking-cost / wall-time
tradeoff, not a general claim of a faster elapsed checker. Native CPU estimates
vary across these short studies and do not establish a practical CPU speedup.

## Correctness boundary and preserved UNKNOWN

All 39 source library tests and 16 raw source-record controls pass for the
selected source. Both one- and two-worker portable attempts complete all 230
prescribed inputs: 229 have the expected raw verdict; `magma-list-pair-n21`
is killed by SIGKILL. No missing verdict is normalized into rejection or success.
An isolated matched replay also SIGKILLs the unchanged released-source binary
and candidate near 5.5 GiB RSS (5,753,552 and 5,751,704 KiB). This supports a
local resource explanation without proving the exact cause or closing the case.
The qualification launcher remains failed, with both failed attempts retained.

Complete current Mathlib, the nine other large exports, native-target hardware
instruction measurement and official Arena rank remain UNKNOWN. The prepared
workflow fixes both released baseline and candidate at two workers; alternate
worker counts remain separately recorded diagnostics. It retains strict acceptance, instruction,
CPU and memory gates. No ranking change is inferred from the prefix.

`decision.json` binds source, executable and input hashes, raw measured ratios,
selection, negative results and missing gates. Reproduction uses `build.py`,
`screen.py`, `pgo.py`, `workers.py`, `qualify.py` and `stress_control.py` with the
paths recorded by their receipts. `compare.py` and `portable.py` reuse the
retained exact-input full/portable comparators with explicit worker identity.

The Apache-2.0 sokonanoda origin and notices remain unchanged. No competitor
checker implementation is copied; Init training uses the previously credited
public data asset. Individual component results do not qualify the combination.

## Promotion interpretation

The existing two-worker configuration remains the promotion baseline and
candidate setting. The one-worker result is retained as a diagnostic tradeoff
and is not promoted as a practical speed improvement when elapsed time grows.
The prepared full-input workflow therefore compares both executables with two
workers and evaluates wall time, CPU, memory and correctness. General changes
to thread-count policy require discussion before being used for promotion.

## Remaining-overhead experiment

Inference inlining produces a byte-identical executable, both with and without
the smaller prune memo. It has no executable effect for this compiler/build.
Reducing the prune memo from 256 KiB to 64 KiB per worker gives an instruction
ratio of 1.000024 versus the selected stack: no additional cost saving, against
a prospective 1.854% threshold. The unchanged selected stack again measures
9.870% fewer prefix instructions than the released-source control.

An exploratory four-round native sample suggested 5.253% lower elapsed time
for the smaller cache. A new 12-pair native sample failed its predeclared
confirmation rule: only 5/12 pairs improved, median wall ratio 1.014523 and
median CPU ratio 1.017427 versus the parent. The smaller cache is rejected for
the selected stack; its initial positive sample remains preserved.

The same new sample measures the selected stack at median paired wall ratio
1.049842, CPU ratio 1.050062 and peak RSS ratio 1.548659 versus released source.
Thus the instruction-cost improvement does not establish a practical speedup;
the latest bounded native sample is slower and uses more memory. Full-input
performance and complete qualification remain UNKNOWN. The selected kernel
source tree and two-worker setting are unchanged. Further additions need to
improve actual work or reuse and pass the full-input practical resource gates.

`remaining_overhead.py` reconstructs the extra source arms; `screen.py` records
their controlled instruction comparison. `remaining_native.py` records the
independent native confirmation. `remaining-results.json` binds protocols,
summary observations, exact executable identities and rejection decisions;
the retained evidence archive also contains every raw output and failed sample.
