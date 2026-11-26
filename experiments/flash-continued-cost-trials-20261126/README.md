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
| eval_node | 13.249% |
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

The next isolated experiment tests Init-trained compiler PGO on unchanged
source. See `../flash-init-pgo-20261126/`; no PGO performance result is assumed.
