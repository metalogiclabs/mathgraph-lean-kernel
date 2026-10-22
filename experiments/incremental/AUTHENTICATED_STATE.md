# Authenticated export state

`authenticated_state.StateChainSession` extends the existing accepted-predecessor
adapter. It retains the producer, native typed index, conservative applicability
predicate, genuine retained Rust kernel, HMAC issuer and MathGraph evidence
boundary. It changes the representation of the accepted export.

The earlier `RevisionChainSession` still materializes, hashes and reads back a
complete sealed export on each update. Its receipt domain and default behavior
are preserved. The new mode admits the same fully checked, exact-SHA-pinned
genesis, then retains immutable declaration slices and authenticated delta bytes.
An accepted state ID addresses a construction containing the exact parent state
and evidence, delta, authenticated transition, source root, policy and revision.
It is **not** the SHA256 of the constructed full NDJSON file, a semantic-equivalence
claim, or evidence that checking occurred by itself.

## Acceptance and recovery

1. The existing source owner captures all six bounded local source files and
   compares the actual produced environment. A reported name or patch is not
   authority. Imported Lean/Std and the toolchain remain pinned.
2. The existing HMAC policy authenticates the exact parent, delta and provenance.
   A separate transition domain binds a parent **state ID**.
3. The native index and retained kernel parse every changed DAG row, even if
   zero obligations are selected. Uncertain graph transitions use the existing
   conservative full-index path.
4. The unchanged applicability predicate selects obligations. Only an actual
   successful selected kernel check permits issuance of a state receipt.
5. That receipt reconstructs the typed index from the authenticated parent and
   uses the same applicability predicate. The adapter persists the source
   capture and signed head before promoting the accepted in-memory state.
6. Recovery requires the caller's expected head, authenticates every persisted
   object and parent link, regenerates source-owned deltas and genuinely replays
   selected checking. A valid historical prefix is not a latestness authority.

State and legacy full-export receipts have different schemas and authenticated
domains. Neither may be substituted for the other. Every nonempty delta must
preserve newline framing. Metadata, schedule, kind and old name-DAG mutations
are refused at the representation boundary; the native parsers retain their
independent validation duties. Rejection or a persistence failure poisons the
speculative processes and does not promote a head.

## Interface

Construct/start/apply/close and expected-head recovery follow
`RevisionChainSession`. Successful results expose `state_id`; `export_sha256`
is explicitly `None`. Declaration decisions retain the existing
`VERIFIED_NEW`/`VERIFIED_REUSED` distinction and dependency witnesses. Evidence
identifiers denote actual newly checked or previously warranted acceptance.

`materialize_current()` explicitly produces and seals the accepted full export,
computes its actual file SHA256 and reports its measured cost. It runs outside
the warm acceptance path and grants no new acceptance. `materialize_attempt()`
can export a staged rejected candidate solely for an independent oracle. It
reports no accepted state ID and binds the attempted parent state and delta;
the previous accepted snapshot must never stand in for a rejected input.

The immutable retained bytes are private issuer-owned state, under the existing
source-owner assumption. Corrupt disk storage cannot mutate those already
admitted private bytes; persisted content-address checks and cold replay refuse
corrupt objects. This is neither a revocation service nor protection against a
compromised issuer, process, kernel implementation or secret key. HMACs do not
prove semantic equivalence.

## Cost and qualification boundary

Warm recipe updates visit changed rows and bounded local replacement slots.
They do not read, serialize or SHA256 the complete successor export. Initial
admission, explicit full export and cold history replay remain substantial
operations. The native implementation still clones/scans retained index data,
and Python receipt reconstruction and applicability still visit whole-index
structures. Complete verification is therefore **not** claimed asymptotically
proportional to the changed dependency cone.

`test_state_representation.py` covers serialization and receipt domains; its
fixtures are not kernel verdicts. `test_authenticated_state.py` compares exact
full bytes, typed indices, dependency decisions, real fresh Rust and cold
recovery on both pinned workloads. New controls and three-arm repeated lifecycle
measurements are supplied by `test_state_controls.py` and
`benchmark_authenticated_state.py`. All earlier qualification gates continue
through the dedicated workflow. A qualified result requires the exact-source
CI and independent artifact replay; local smoke success alone is insufficient.

No new theorem proves the executable serialization/parser/issuer bridge. The
previous bounded reuse model and the independent full-kernel comparisons retain
their stated scope.
