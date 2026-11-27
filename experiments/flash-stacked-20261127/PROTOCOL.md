# Measure the stack rather than adding separate percentages

Base: released bc704eebed4e009bc66af1a849f18315c11f1926. The local projection
candidate c8c2778 is qualified only on the fixed prefix and 230 portable inputs.
Existing full-input single-change measurements are lineage, not stack results.

- [x] Reconcile the current research state and preserved negative results.
- [x] Build independent exact-source cumulative combinations.
- [x] Measure every combination against released source and projection alone.
- [x] Select the smallest consequential instruction-saving combination.
- [x] Test fresh Init-only compiler training on the selected source.
- [x] Verify 39 source library tests and 16 source-record controls.
- [ ] Close broad qualification: each worker count has 229 correct outcomes plus one SIGKILL UNKNOWN; preserve matched unchanged-baseline SIGKILL control.
- [x] Measure the worker-count tradeoff separately.
- [ ] Run complete current Mathlib and the nine other large cases.
- [ ] Obtain official native retired-instruction scoring.

Arms: baseline; projection; projection+eval_node inline(always);
projection+inline+512-declaration scheduling batches;
projection+inline+18 MiB value budget;
projection+inline+36 MiB value budget;
projection+inline+512 batches+36 MiB budget.
There is no frame-copy, failed skip/reuse, front cache or context-span prototype.

All arms compile sequentially from the same absolute source/target directory,
compiler, dependency lock and generic x86-64 flags. This controls source-path
and crate-identity differences as well as freezing actual executable hashes.
Source identities before/after compilation and complete patches are retained.
All 16 raw source-record controls must pass per arm before cost measurement.

The prefix is the original 134,232,002-byte / 25,131-declaration Mathlib input,
SHA-256 c3d1e08032bbfe2dbfc4c8a84fd711ba83296a47d7468d9ce15988efa4acfa3a.
The original calibrated DynamoRIO client is used, never the rejected TLS client.
Two identical-executable controls for both baseline and projection are measured
before candidate observations. The reduction gate is max(1%, twice the larger
fractional control range). Two alternating paired observations must each clear
that gate against projection alone and against baseline. Raw total ratios,
per-arm increments, CPU, wall and peak RSS are retained. Four additional native
rounds follow counting; noisy short timings never become a CPU speedup claim.

If two stacks differ by less than the gate, prefer fewer source modifications;
for otherwise indistinguishable budget variants prefer the smaller budget.
Broader correctness is run on the resulting selected source, not inferred from
qualification of its components. A complete-Mathlib stage remains necessary;
single-change prefix overestimates (batch512 2.33% prefix vs 0.836% full input)
are preserved. A larger value budget's previous native CPU regression is not
erased by its instruction gain.

Fresh PGO uses the selected exact source and only the fixed public Init data
asset already credited in flash-init-pgo-20261126. Train one- and two-worker
executions using atomic profile updates, with explicit Cargo host target to
exclude host build profiles. No Mathlib measurement enters training. Init is
part of Mathlib's foundation, so this is not an out-of-distribution claim.
Compare fresh PGO to the identical-source non-PGO binary, not a differently
configured kernel. Any profile mismatch is a failed apparatus gate.

One-worker measurements vary argv only on the selected executable and report
the wall-time tradeoff. Source changes, compiler changes and worker changes
remain separately attributable. No Arena seconds or rank are extrapolated.

For complete-input promotion, keep both executables at two workers and require
the existing acceptance, instruction, CPU and memory gates plus at most 3%
median elapsed-time regression. Record both wall-time pair ratios. Report a
practical wall-time improvement only when median elapsed time falls at least
1% and both alternating pairs improve. This condition is declared before any
complete-input candidate observation; prefix instruction savings do not pay it.
