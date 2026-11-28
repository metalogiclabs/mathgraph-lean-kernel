# Continued cost trials on the qualified Flash source

Parent: `bc704eebed4e009bc66af1a849f18315c11f1926`, source tree
`06c257f0f2ff1f64711cfa54620b650e6dd59b7e`. The qualified checker is unchanged.

The complete frozen-binary profile was independently downloaded and verified:
[run 45717337815](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45717337815),
artifact `15070987546`, SHA-256
`150792eb39f9807f44cdf22342640350a0e0c4681dc220b4a82e9ae59672ca4d`.
Its checker executable remains `09fe7ecf7421be7ad7f7c57596c214bcd6e7c0d912d6d555cb5749b17202bd5b`,
the input is the exact 6,326,141,213-byte Mathlib export, and all 739,167
declarations ACCEPT with raw exit zero. Calibration totals are exact and
the exclusive symbol buckets sum to the raw total 546,073,810,215.
The attribution is by compiled symbol; inlined work belongs to its enclosing
symbol. It is not a call-tree or source-level causal decomposition.

| Exclusive compiled symbol | Share |
| --- | ---: |
| eval_no_cache | 20.515% |
| eval_node | 13.250% |
| infer_nonvar | 12.700% |
| prune_env_cold | 9.596% |
| Vals::intern_frame | 5.118% |

This motivated isolated, independently authored follow-ups. Every comparison
below uses the same SHA-pinned 25,131-declaration, 134,232,002-byte prefix,
one checking worker, distinct executable hashes, three analytical loop
controls, and two alternating pairs. All four executions ACCEPT; all 16
actual source-record controls match their required raw outcomes.

| Trial | Software instruction change | Decision |
| --- | ---: | --- |
| 64K exact-key prune memo | +2.757% | Reject as a prefix performance priority |
| 256K exact-key prune memo | +14.549% | Reject as a prefix performance priority |
| Mixed application chain, first single-pass prototype | +0.118% | No useful gain |
| Mixed application chain, split uniform/mixed phases | -0.308% | Retain candidate; no whole-input promotion |
| 4K exact-key prune memo | -0.502% | Retain candidate; no whole-input promotion |
| Avoid evaluating syntactically unused lambda arguments | +0.028% | No useful gain |

The unchanged parent has a 16K-entry memo. Cache keys remain the full exact
environment ID and dependency mask in every capacity variant. The chain
trials preserve application order; their typed controls distinguish two data
values rather than relying on proof equality. The unused-argument prototype
also checks that erasing an argument during reduction cannot authorize an
ill-typed application. It leaves type inference unchanged.

The final chain trial retains its 42-test library log, the 4K memo its
39-test log, and the unused-argument trial its 43-test log. Their retained
raw-export integration tests cover eight actual exports. The optional empty
corpus test is not counted as a corpus replay, and three existing doctest
examples remain ignored. Earlier per-trial native-suite logs were not
retained; no additional native-suite warrant is inferred for those trials.
The initial 64K build stopped for insufficient disk space, then the same
source was rebuilt after deleting only reproducible local compilation
intermediates. That availability failure precedes any checker measurement.

All whole-Mathlib effects remain UNKNOWN. Prefix software instruction
changes are not CPU time, official retired instructions or Arena rank, and
the percentages cannot be added together. No prototype changes the pending
official source revision or release descriptor.

## Official submission independently rechecked

[Arena PR398](https://github.com/leanprover/lean-kernel-arena/pull/398) is open
and ready for review, pinned to the already qualified checker source.
The raw [official PR run 45722992953](https://github.com/leanprover/lean-kernel-arena/actions/runs/45722992953)
was independently rejoined to its own input-stat manifest: all 231 prescribed
outcomes are correct (139 accepts, 92 rejects); 28 of 30 policy cases return
a permitted decision and two time out. A filename under `corner-cases/`
does not by itself imply an optional outcome: `proof-param-ok` is prescribed.

`official-pr398/` preserves the receipt verification script, all compact
verdict/input identities and the recomputed digests of all 522 raw result
and input-stat records. To rerun verification, download artifacts
`15072279691` and `15073935467` as `results-mathgraph.zip` and `test-stats.zip`,
extract them under `raw/` and `test-stats/`, then run `verify_official_pr.py`.
Both original archive SHA-256 values and CRC checks are enforced.

This is receipt verification, not a fresh checker execution. The PR workflow
skips Mathlib and several other large inputs. Its 231 outcomes overlap the
older exact 230 portable/240 complete qualification and cannot be added to
those counts. Official full-Mathlib scoring and a new rank are outstanding.

The completed Init-trained compiler PGO experiment uses unchanged source.
See `../flash-init-pgo-20261126/verified-comparison/`: complete-input software
instructions fall by 1.413%, while the two native CPU pairs disagree in
direction. The other nine large-input PGO verdicts remain unqualified.


## Further residual tests

A seventh isolated trial routes shallow argument chains through ordinary
memoized evaluation while retaining the iterative path for deep chains.
Its right-depth metadata fits the existing 32-byte expression node, and
44 library tests, eight retained raw exports, all 16 source controls and
four prefix ACCEPTs pass. It nevertheless costs **3.838% more** prefix
software instructions and is not promoted. This measures the combined
metadata/evaluation change; it does not isolate a single cause of the loss.

Two observation-only builds measured environment shape on the fixed prefix.
They are excluded from every speed comparison. Across 3,604,409 new Cons
environments, pruning skips 8,872,539 bindings in 3,264,561 runs (mean 2.718);
only 6.640% of runs skip at least eight bindings. Of 4,116,927 frame calls,
only 4.848% are index-zero singletons without a rest environment. These
observations disfavor prioritizing a jump pointer on every new Cons or a
special singleton-zero representation. They do not reject those ideas on
whole Mathlib. Patches, actual instrumented stdout/stderr, binary hashes and
histograms are retained under `environment-shape/`.

A separate worker-count experiment preserves the identical executable and
varies only its explicit argv. Its six prefix ACCEPTs indicate 4.540% fewer
software instructions with one worker than two, versus 2.794% more with
four. Exact loop controls and explicit one/two/four-worker loop-coverage
controls pass. The completed generic recovery on the original frozen binary
reduces this estimate to 1.929% on complete Mathlib. See
`../flash-worker-counter-recovery-20261126/completed/`. The separate native
study trades 3.413% less CPU for 76.569% longer wall time; its instrumented
native SIGILL remains unresolved. No submitted defaults change.


## Further context-lookup residual

A third observation-only build records 1,411,356 type-context lookups and
an index-plus-one upper bound of 12,032,954 parent-walk steps (mean 8.526)
against 761,372 new contexts. An isolated contiguous-span prototype passes
41 dev-profile library tests, eight retained raw exports, 16 release-binary
source controls and four exact-prefix release-binary ACCEPTs. It saves
only 0.513% prefix software instructions. The release library-test build
was SIGKILLed; that suite is UNKNOWN, not passed. The first baseline-only
counter attempt was also SIGKILLed; its failed receipt is retained and
excluded from the successful repeat. Exact causes remain unresolved.
No complete-Mathlib or rank result is inferred; the prototype is not promoted.

Completed PGO and native worker results are retained in their separate
experiment directories. PGO saves 1.413% whole-input software instructions
on unchanged source. One worker saves 3.413% native CPU versus two, with
76.569% longer wall time; its native instrumented execution failed with
SIGILL. Six retained register/carry controls pass but do not resolve that
failure. Do not conflate these outcomes or add their percentages.
