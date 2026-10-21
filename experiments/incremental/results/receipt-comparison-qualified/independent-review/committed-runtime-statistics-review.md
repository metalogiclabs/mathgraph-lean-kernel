# Read-only review of committed equality and economic gates

Source `5dfe38b01ca7b1c67f70be4ffb2479978049239e`, compared with
`6e717043b85acdad63c2399131cb5f9a7432ee37`. No CI result is inferred here.
The portable artifact reviewer remains frozen at
`fb6943f4c36126b16e9f36d87e1a18da0f4a2ffc35632ecc7d4e4f08960f801a`.

No in-domain equality false positive was found. The runtime diff adds
`_same_index_json`, a validated comparison mode, its signed policy field and
the single post-authentication comparison. `authenticate_sparse_acceptance`
still checks the receipt content ID, HMAC/domain/status/fields, reconstructs
against the verified baseline, validates the obligation list and reapplies
`engine.reuse_decisions`. The real selected checker, materialization,
canonical signing, durable record and cold authenticator remain intact.

For admitted acyclic plain JSON, the helper preserves the canonical comparison:
scalar types differ through the legacy encoder; integers and booleans are not
coerced; floats preserve legacy signed-zero/NaN formatting through fallback;
unequal non-ASCII strings and non-ASCII/non-string object keys fall back;
ASCII string equality and ASCII key-set equality are injective under the old
encoder; list order remains significant. Exact shared dict/list identity skips
only a subtree of the private admitted baseline. This is an operational trusted
memory assumption already present in frozen-baseline reuse. It does not
validate arbitrary Python objects, concurrent mutation, cycles or excessive
depth. The source document states that narrower boundary and the observed
real index depth4; its independent differential fixtures remain bounded tests.

The harness uses the same actual retained checker, binary pins and source
workload in both arms. It alternates arm order per repetition/edit and shuffles
edit order deterministically. Independent direct full Rust runs after apply
on the same sealed snapshot and before full-index oracles. Representative
compression is deferred until all warm pairs finish. The default mode's
protected controls and bidirectional cross-mode refusal are separate gates.

`qualify_delta.paired_economics` computes candidate/control ratio of medians,
10,000 paired-index resamples, order-statistic 95% interval, and strict
majority pair wins. SPEEDUP requires ratio<1, majority wins and upper bound<1.
The receipt harness fixes five pairs per case; its wrapper replaces inherited
scope labels with actual wall, CPU, kernel, persistence, setup-component or
same-snapshot direct-Rust comparators. These are pointwise finite-host-repeat
intervals, not simultaneous confidence across all phases/profiles or a
cross-host population claim. Five pairs provide limited precision. Any
individual selected-kernel phase difference is incidental to this Python
comparator experiment and cannot be promoted as a changed Rust kernel.

Correctness publication is independent of economic status. A legitimate
NO_SPEEDUP does not fail publication; missing/failed gates, a partial matrix,
source/tool drift, wrong policy, incorrect refusal causes or oracle failures
do. `statistical-gate-review.json` explicitly exercises a consistent synthetic
2x-slower candidate: economic NO_SPEEDUP is accepted, while a false issuer-audit
flag still refuses. This diagnostic is not measured performance evidence.

Complete warm apply excludes constructor/startup and shutdown. Setup plus one
apply is an explicitly named component sum, not full lifecycle time or
multi-update amortization. Cold replays are observed separately for both modes.
CPU includes adapter and completed/live child counters with tick granularity.
Memory remains post-phase procfs RSS/HWM with cumulative startup HWM and absent
exited processes; no aggregate/phase peak-saving claim is supported. Complete
receipt reconstruction, second reuse, export materialization/hash and the
declaration-list scan remain O(N). Actual CI source/content/arithmetic review
is pending its provider metadata and archive.
