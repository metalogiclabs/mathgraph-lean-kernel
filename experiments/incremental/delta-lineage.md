# Authenticated producer delta: source lineage and qualification boundary

This experiment continues qualified source
`c5ab12699338aa57b7e9d48b15d4a7409e453c7b` of
`metalogiclabs/mathgraph-lean-kernel`. It reuses the selected checker, typed
identity/dependency engine, conservative reuse predicate and existing issuer-key
authority. A producer attestation authenticates identity and completeness under
its stated trust boundary; it does not establish kernel acceptance.

## Existing qualified implementation

[Canonical checkpoint](https://app.notion.com/p/3fb3e523d7ab81c68c89c1442eb0bb05)
and [exact-source run 38885278602](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38885278602)
retain 197 original gates, 335 native differential gates, 719 independent replay
checks and 251 benchmark correctness gates. The early edit checks 413 and reuses
3,023 of 3,436 obligations. Changed-input total verification still loses to
direct fresh Rust. Runs 38879576999 and 38881665840 are withdrawn acceptance
evidence because pipelines ending in tee masked failed required checks.

The earlier native observer is a faster complete scan. Export generation,
whole-byte hashing, full identity work and complete receipt construction are
separate costs. The present experiment must report which costs it removes,
which it amortizes, and which remain proportional to the whole development.

## FLASH: qualified admission before existing consequence propagation

[Source checkpoint](https://app.notion.com/p/3f73e523d7ab818f86ddf4340306b016).
Qualified implementation:
[`7133a5b4cfa66f9b91de522c534fd4f4431331e6`, crossrepo_event.py](https://github.com/heathsanchez/test/blob/7133a5b4cfa66f9b91de522c534fd4f4431331e6/research/flash_v14_real/crossrepo_event.py).

- `load_qualified_engines` checks the independent consumer, its tests and the
  existing FLASH engine against exact source blobs.
- `facts_from_pinned_graph` transports actual typed source routes without extra
  semantic edges.
- `ExactCrossRepoBridge._verify_sources` checks producer/notice bytes and invokes
  the actual independent consumer.
- `admit_from_verified_source` authenticates admission before calling existing
  `RecloseEngine.apply`.
- `checkpoint_and_restore` independently rechecks source authority. A checksum
  on compiled state grants no authority by itself.

Fresh read-only inspection of decoded logs for
[run 38208892583](https://github.com/heathsanchez/test/actions/runs/38208892583),
job 114678412099, confirmed actual exact-byte validation, eleven unmodified
RealityGraph consumer tests and both real event/restart PASS markers. One exact
bounded claim changes through admission, controlled local trust withdrawal and
source-checked restoration; six unrelated claims stay unchanged. The producer
is MathGraph `040456fc8862c79c8b384ce63846628274b678be`, consumer RealityGraph
`9b3189a64825e2cb6ebc7b5c17f5f193bdf5cfe3`, existing FLASH V13 engine
`90d167031bba230399a686252ae5573d57100b94`.

This supplies an existing source-evidence admission pattern. It does not
qualify arbitrary source-dependency extraction, a Lean producer-delta protocol,
continuing freshness, or a new Lean proof.

## Nucleus: source-owned immutable environment publication

[Source checkpoint](https://app.notion.com/p/3f83e523d7ab81928d93fa205b649bd8).
Retained qualified production is `heathsanchez/test`
`de95855135d5c5fe8916b7ea005e736146bc5064`, implementation tree
`95ff1325d8d27778019f07bff222e0b096c40377`.

[`Environment::extend_owned`, environment.rs](https://github.com/heathsanchez/test/blob/de95855135d5c5fe8916b7ea005e736146bc5064/metatron-kernel/src/environment.rs#L167)
consumes its environment and uses `Rc::make_mut` for constant/body maps.
Duplicate-name and authority-overflow validation precede writes. Unique maps
avoid copying all prior entries; retained snapshots and machine map witnesses
force copy-on-write. The borrowed `extend` interface preserves old snapshots.
[`check_export_with_policy`, checker.rs](https://github.com/heathsanchez/test/blob/de95855135d5c5fe8916b7ea005e736146bc5064/metatron-kernel/src/checker.rs#L421)
publishes established declarations through this owned operation.

Tests cover 2,048 unique appends retaining map allocations, retained snapshots,
duplicate/overflow failure, sibling separation and old machines never seeing
future appends. Crucially, siblings can have the same numeric `AuthorityId`
counter and different bodies: that counter is not an authenticated unique
environment root. Source-owned in-memory publication also does not establish
portable persisted acceptance.

Fresh read-only inspection of
[run 38510602017](https://github.com/heathsanchez/test/actions/runs/38510602017)
confirmed all default/origin/demand jobs and their required steps succeed.
Decoded origin job 115677973078 actually reports 119 ACCEPT, 71 REJECT,
6 UNKNOWN, zero wrong and zero execution errors. The earlier owned-environment
snapshot reports 325 passing tests and local matched Init child CPU
1.79043 to 1.689705 seconds; the retained predecessor repair reports 326 tests.
Six targeted complete exports remain UNKNOWN. Unpromoted later ownership,
introduction and cache experiments do not supply a new whole-export result.
No Nucleus full-Mathlib acceptance or Arena superiority is inferred.

## Producer-delta boundary to qualify

The installed `LeanExport.dumpEnv` already selects roots and their dependencies;
fresh `M.run` tables and `initState` scanning do not certify omitted declarations
unchanged. Existing stream IDs are local to an export. Source pins and inspected
functions are recorded in `results/native-qualified/producer-delta-residual.md`.

The new authenticated update must bind the accepted old environment, complete
new ordered environment and complete mutations, including visibility,
metadata, builtin assumptions and original mutual-inductive boundaries. Actual
changed bytes still require genuine parsing even with no selected obligations.
The external full index and Rust/C++/paranoid checks remain independent oracles;
the producer's root, an index equality, and a reuse count cannot establish
acceptance on their own.

`qualify_delta.py` records correctness separately from economics. Session
seeding is a separately measured baseline cost; timed apply includes producer,
delta identity, selected checking and receipt persistence. The direct comparator
checks the same live sealed composite snapshot. Warm-session measurements do
not establish cold-command superiority or change-proportional total lifetime
cost. Missing controls remain explicitly UNKNOWN, and an unsuccessful economic
gate is reported as NO_SPEEDUP rather than hidden as a correctness failure.

The opt-in `std-hashmap-expanded-v1` profile is pinned separately in
`delta-pins.json`: 5,318 explicit roots and 11,653 flattened obligations. Its
five expected full-export identities come from the original separately compiled
source variants and bundled `leanexport`; `expanded-roots.json` is itself
content-pinned. Original source/toolchain pins and the original 3,436-obligation
qualification remain intact. The harness reports each workload separately;
larger-profile results cannot erase an original-profile economic negative.
Expanded work counts come from fresh complete indexes, independent partition
replay and actual selected-kernel output, rather than assuming the original
413/3,023 partition scales unchanged.

The current bounded API admits one update anchored at an authenticated baseline.
Cold replay rebuilds retained producer/index state, reauthenticates old evidence,
and repeats actual checking; it does not imply a general arbitrary-revision
incremental service. Constructor binary capture, session initialization and
baseline checking are included in separately reported setup wall time. The
complete acceptance receipt currently still contains the complete typed index;
the harness measures its actual bytes. Changed export persistence does not make
that full receipt or SCC reclosure proportional to the changed cone.

Qualification includes deliberately signed producer-bug fixtures for invalid
proofs, invalid standard-axiom types and unused malformed typed input. They are
explicit NDJSON-boundary fault injections, not Lean source proofs. Even with
zero selected obligations, the actual selected parser and separately invoked
zero-selection parser must reject unused malformed input. Independent full
Rust, normal C++ and paranoid C++ checks consume the identical sealed composite.
Issuer/HMAC, source-region, input/environment/version, foreign-authority and
actual persisted-object corruption controls remain separate from those parser
and inference checks. Rejected runs do not claim all scheduled checks completed.
