# Retained SCC identity transition implementation

- `red.log`: the first contract tests failed because retained preparation/state did not exist.
- `green-initial.log`: initial reverse-cone and edge/negative-dependency fallback contracts pass.
- `green-adversarial.log`: cycle, SCC member, restoration, global/builtin, sparse-name, no-op, and existing poison/parser-boundary tests pass.
- `green-release-lib.log`: all 63 ordinary library tests pass; the real-input finish microbenchmark is explicitly ignored unless selected.
- `build-index-session.log`: release protocol executable build.

`IdentityBuilder::finish` is text-identical to the baseline full oracle. The default session
cold path runs it once to establish the initial index and then constructs the owned
SCC/condensation/reverse graph. This second cold graph traversal and cache preparation are
included in ready.prepare_wall_seconds. Forced-full ready and updates do not prepare a
retained graph. No graph/cache deserialization is supported.

Fast admission requires exact full direct-dependency fingerprints, including unresolved
negative name keys. Added builtin name rows are tracked by actual insertion events,
including sparse indices below the prior names vector length. Changed axiom assumptions
or builtin declarations trigger the full oracle. Metadata, declaration-kind/name/schedule
and complex declaration updates retain their existing refusal/poison behavior.

The retained timer covers guards, reverse-cone discovery, dependency-first SCC hashing,
changed declaration own fingerprints, affected closure slots, and builtin closure slots.
Affected-key/statistics output construction, full JSON serialization/IPC, are outside this computation timer. The separate finish_wall_seconds and finish_cpu_seconds
fields cover the complete post-parse call, including statistics and cleanup. The immutable
topology now remains alive through response emission using an Arc held by its owning
IdentityBuilder. Closing that session releases the topology; shutdown remains a real
end-to-end/lifecycle cost. This first phase retains the complete index response. It does not claim
O(cone) total request cost or a sparse IPC/receipt protocol.

The same-parsed-mutation microbenchmark is an ignored test:

```
RETAINED_BENCH_EXPORT=/path/baseline.ndjson \
RETAINED_BENCH_DELTA=/path/producer-delta.ndjson \
RETAINED_BENCH_REPETITIONS=7 \
cargo test --release --lib benchmark_retained_finish_same_parsed_mutation \
  -- --ignored --nocapture
```

It parses/mutates once, alternates measurement order, restores private baseline graph
clones outside each compute timer, and compares the entire resulting index against the
untouched full finish on the same parsed mutation. Clone/reset work is deliberately
excluded and disclosed; use actual index-session wall-time samples for complete updates.
Cyclic unit fixtures test identity equality only, not proof acceptance.

All retained state is private process-owned data initialized from the parsed baseline.
The producer/consumer issuer and downstream checker retain responsibility for baseline
provenance, authentication, and proof acceptance. Arbitrary in-process memory corruption
is outside this boundary; this code does not claim to detect it or authenticate memory.


## Whole-call and lifetime correction

Pre-Arc seven-repetition same-parsed-mutation medians for the unrelated-definition cone
of one declaration were 14.4/20.0 microseconds of core work but 534/2397 microseconds for
the entire finish call (3436/11653 declarations). This exposed per-entry graph destruction
after the original core timer. Pre-correction logs and source are retained in `pre-arc/`.

The corrected implementation keeps immutable topology in an Arc owned by the builder
until session close. `retained_topology_lives_until_the_owning_session_is_dropped` uses
Weak references to show that the topology remains alive after fast finish and is released
when the builder is dropped. No retained state is accepted from disk or IPC. Mutable SCC
root fingerprints and the response index remain private owned values. Final microbench
logs are in `post-arc/`; they still disclose graph/index clone/reset work outside timing.
Full index JSON serialization/transfer and all session shutdown costs remain separate.
