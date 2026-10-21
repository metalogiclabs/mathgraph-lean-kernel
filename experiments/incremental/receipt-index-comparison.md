# Canonical receipt-index comparison without full serialization

This experiment continues the retained-parser issuer-admission candidate
`6e717043b85acdad63c2399131cb5f9a7432ee37` and its exact-source CI
[38995206988](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38995206988).
That run established bounded correctness but its early-edit complete warm A/B
comparisons were **NO_SPEEDUP** on both workloads. Only the small unrelated
case qualified against the existing fresh-selected adapter. Its protected
comparison against direct full Rust was a different experiment. Kernel-phase
savings must not be promoted as whole-pipeline savings.

## Smallest measured gap

Sparse receipt issuance already reconstructs its just-signed receipt, verifies
its HMAC/content address, and reapplies the unchanged reuse predicate. It then
serialized both the reconstructed and live complete indexes solely for equality.
An actual expanded early-edit diagnostic measured two 20,117,094-byte encodings,
70.431ms and 69.480ms. The genuine retained kernel accepted; fresh full Rust,
Lean C++ and paranoid C++ accepted that exact sealed input independently.
These instrumented observations locate a cost; they are not a qualified speedup.

The change replaces only this final equality operation. Authentication,
reconstruction, the second reuse-predicate application, selected checking,
canonical signing/content addressing, sparse receipt format, durable persistence,
source producer and independent oracles remain intact. Rust checker, parser,
identity engine and MathGraph resolver are unchanged from the candidate.

## Equality boundary

The compared trees derive from native parsed JSON indexes and shallow baseline
patch reconstruction. They are already admitted, acyclic, serializable JSON;
this helper is not an input validator or equality for arbitrary Python objects.
Their shared private baseline subtrees can be identical without serialization.
Lists retain order, object keys retain their canonical meaning, and differing
scalar types never use Python's coercive numeric equality. Floats, unequal
non-ASCII strings, non-ASCII/non-string object keys and unsupported containers
fall back to the existing canonical encoder. This covers signed zero, nonfinite
float representations and astral/surrogate aliases.

All eight measured real index shapes have depth4, exact ASCII string object
keys and plain JSON values. Unicode declaration names do occur. Native parser
and typed patch policy bound admitted input; arbitrary cyclic or deeply nested
Python object graphs are not accepted state. An independent depth500 probe
raises a conservative recursion error outside that observed schema, while the
legacy encoder can serialize that artificial tree. No generic equivalence
claim is made for that domain or for concurrent/process-memory corruption.

Both `shared_json` and original `canonical_json` comparison modes enter producer
provenance. A previous mode's receipt/session does not silently become compatible.
The public cold sparse-receipt authenticator is unchanged. Shared object identity
is a computational shortcut under the existing trusted-process boundary; it is
not new evidence of semantic equivalence or permission to reuse a declaration.

The retained native parser remains a separately added semantic TCB: it checks
the admitted baseline-plus-delta AST, while the materializer builds the sealed
complete export. Fresh full oracles qualify their correspondence on the bounded
cases; the old Lean model does not prove that executable bridge.

## Qualification and measurement

`test_index_json_equality.py` compares against the actual canonical encoder on
numeric/Unicode/container adversaries, shared declaration-shaped trees and
deterministic generated JSON. Independent differential review additionally uses
all eight artifact-matched real indexes and mutates fingerprints, dependency
witnesses, names, schedules and scalar types.

`benchmark_retained_admission.py --mode receipt-compare` compares the two equality
modes with the same genuine retained kernel, admitted baseline, producer,
authentication and reuse predicate, using five alternating pairs per early and
unrelated edit on the pinned 3,436- and 11,653-obligation workloads. Complete warm
producer-to-persistence, actual direct full Rust, phase CPU/wall/memory, cold
restart and exact selected/verdict/receipt parity are separate observations.
The pinned `incremental-receipt-comparison.yml` workflow preserves the inherited
correctness suites and negatives, source/executable stability, independent full
oracles and fail-closed publication. A legitimate NO_SPEEDUP remains publishable
as a negative; missing or inconsistent correctness evidence is a failure.

Results require the exact completed source/run/artifacts and independent review.
No speedup is qualified by this source document or by the local diagnostic.
This still scans the declaration list for equality and keeps full receipt
reconstruction, repeated reuse decisions, complete materialization/hash and
cold initialization. It does not establish change-proportional total work.
