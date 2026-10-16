# Existing MathGraph capabilities and the incremental Lean boundary

Read-only repository audit on 16 October 2026. The audited MathGraph checkout is
`cf359686c74549a132c7a651cd7aabc7c1a870fe` at
<https://github.com/metalogiclabs/mathgraph>. References below distinguish main,
open research branches, executed local tests, and GitHub metadata observations.
No MathGraph production code or deployments were changed for this audit.

## Existing implementations

| Capability | Concrete implementation | Established boundary |
| --- | --- | --- |
| Typed warrant closure | `mathgraph_check/warrant_resolution.py:96` | Least fixed point of conjunctive evidence/premises and alternative routes. Rootless cycles stay `UNKNOWN`; withdrawal removes support. It rescans the supplied graph; locality describes changed outcomes rather than an incremental execution algorithm. |
| Typed relation admission | `warrant_resolution.py:53`, `:131` | A `QualifiedRelation` names an externally admitted formal verifier at the target scope and binds exactly one complete checked route. It is a caller admission boundary, not proof or provenance authentication. |
| Historical source withdrawal | `mathgraph_check/living_warrants.py:52`, `:75` | Exact OpenAI history Git blob, three named publisher withdrawals and an independently admitted JPL record. Documentary support becomes `STALE`; mathematical truth remains `UNKNOWN`. Unrelated JPL support survives. No continuing monitoring. |
| Immutable public evidence | `mathgraph_check/public_receipts.py:77`, `:297` | Exact historical archive pins and externally pinned record digest; case, guard, proof-name, source, normalization, toolchain and axiom-log checks. Recomputing a forged record's self-hash does not qualify it. |
| Independent semantic replay | `conformance/resolve_v1/consumer.py:230` | Separately supplied policy digest, exact three historical members, semantic closure recomputation and producer-result comparison. Supported authority profile is historical and fixed. |
| Offline process isolation | `conformance/resolve_v1/run_isolated.py:74` | Network-denied Docker, read-only inputs, dropped capabilities, unprivileged user, import audit and repeated byte-identical replay. |
| Source occurrence catalogue | `mathgraph_protocol/source_catalogue_v1.py:33`; `tools/mathlib_catalogue/Extract.lean:173` | Stable pinned source identities, direct imports and constants occurring in declaration **types**. Proof bodies are excluded. Relations have authority `NONE`, logical implication false and semantic equivalence false. This is not a complete kernel proof-dependency graph. |

Main's closure API is `Claim(id, kind, scope)`, `Receipt(id, kind, scope)`,
`Route(conclusion, evidence, premises, relation)` and
`resolve_graph(claims, routes, receipts, withdrawn=..., relations=...)`.
Kinds are `formal` or `documentary`. `compare_snapshots` changes lost support
to the presentation status `STALE`; withdrawal itself does not infer refutation.
Receipt construction is explicitly trusted caller work. This API does not admit
a new claim into MathGraph's separate terminal-form kernel.

Open PR137, branch `mathgraph-core-v0-kernel` at
`db42d0e972ca70902147e3ee28d9acd631f9569c`, separately contains a
content-addressed `CoreGraph`, `Support`, `EvidenceReceipt`, `Warrant`, parent
lineage, local revocation and canonical `.mg` persistence. Its successful
[cross-run reuse workflow](https://github.com/metalogiclabs/mathgraph/actions/runs/36668114198)
reuses one prior warranted object with zero Lean/PVS contacts and keeps 24
residual objects unqualified. This is an existing graph capability, not a missing
function to recreate in a compiler adapter.

## External Lean checking already explored

The legacy main adapter is not an independently hardened admission root.
`mathgraph/lean_adapter.py:410` invokes a configured command and file path;
`mathgraph/proof_verification.py:356` treats any configured command's zero exit
as `VERIFIED_PROOF`. The latter's `import_verified_proof:410` accepts a supplied
certificate ID or `provenance.verified=True`. Those hooks assume trusted caller
configuration and do not themselves close exact target-type, axiom-policy,
toolchain or dependency identity. They should not certify the new experiment.

Open PR164, branch `research/lean435-source-verified-receipt-20261014` at
`167bc66556f45ac4bc19a178cef599ede47163e8`, retains a real upstream
`Nat.gcd_comm` experiment. Original qualified test commit
`d009cbe2a0094c0df460e892557150847639372f` has
[successful run 38467582886](https://github.com/metalogiclabs/mathgraph/actions/runs/38467582886)
and [artifact 11850001218](https://github.com/metalogiclabs/mathgraph/actions/runs/38467582886/artifacts/11850001218),
archive SHA-256
`1612a82591d94282acd8869c4420b828114d32240cb4f43970807bc36c863fd0`.
It pins upstream Lean commit `eb6cafb7290e8bd5f2937522d8d804f58f02bafc`
and source Git blob `6b3ac409cc1ed8775644c5c6a00a1a59f96fac2b`,
runs Lean 4.35 paranoid checking/comparison, and requires changed-statement and
forbidden-axiom negatives. It reuses an original theorem; it is not proof discovery.

Open PR166, branch `research/lean435-mathlib-source-transfer-20261014` at
`382f009038981ba11383a68f91a282a7d439defb`, adds
`research/lean435_statement_binding/external_transfer.py`. Its qualification:

1. Pins Mathlib revision, module file blob and Lean toolchain before selection.
2. Selects the first supported syntactically scoped theorem from that file.
3. Generates a declaration using the original environment declaration's
   `source.type` and the original theorem constant as its proof.
4. Requires `SOURCE_STATEMENT_MATCH` from native Lean.
5. Separately compiles a valid proof of `True`, then requires the forged source
   binding to fail with `SOURCE_STATEMENT_MISMATCH`.

[Run 38493357002](https://github.com/metalogiclabs/mathgraph/actions/runs/38493357002)
succeeded for both `Mathlib.Logic.Function.Defs` and
`Mathlib.Data.Nat.Choose.Basic` at Mathlib
`d20f010dc809f2bb8f94969ccc8ed1691bad2531`. Original artifacts are
[11863435383](https://github.com/metalogiclabs/mathgraph/actions/runs/38493357002/artifacts/11863435383)
(`c2b9acbe06c79665593240e36442e658dedda2072b8293c978ad6ba1728251b5`)
and [11863190755](https://github.com/metalogiclabs/mathgraph/actions/runs/38493357002/artifacts/11863190755)
(`9fc44a0d5fe26ee71e74140c76b83cd65f28c1a705fca4b3fbfc02e8b455d0a6`).
Both jobs and unexpired artifact metadata were read back. This specific held-out
Mathlib path uses native Lean; it does not run the earlier paranoid multi-kernel
or explicit permitted-axiom qualification.

Its report schema is `mathgraph.native-mathlib-source-identity-transfer.v1`:
`status`, `source` pins, `selection` name/source hash, exact `steps` commands,
exit codes, diagnostics and log hashes, `source_under_test`, `error`, scope and
exclusions. The earlier schema `mathgraph.lean435-receipt-candidate.v1` also
contains target statement, permitted axioms, checker mode, input hashes and
negative-control observations. Neither is an existing generic production
MathGraph protocol admission receipt.

## MathGraph Check integration

Open PR167, branch `mathgraph-check-github-app-shadow-v0` at
`dcc3c46e4e2a54cfba3dd761bd9e359644c21505`, implements a GitHub App and
Cloudflare Worker/Queues consumer. Actual code verifies webhook HMAC bytes,
narrows repository/head/installation identities, queues accepted events,
rereads current head and CI, mints scoped installation tokens, creates or updates
one App-owned neutral Check, reads it back and revokes its token.

The generic analyzer recognizes exact-head GitHub CI metadata and machine-readable
added-line `UNKNOWN` markers. It labels declarations as author declarations and
does not execute PR code. A successful CI result is not semantic proof.

[Delivery audit 38601432948](https://github.com/metalogiclabs/mathgraph/actions/runs/38601432948)
and [publisher run 38601433237](https://github.com/metalogiclabs/mathgraph/actions/runs/38601433237)
succeeded at the branch SHA. Public GitHub API readback confirmed
[App Check 115974666180](https://github.com/metalogiclabs/go-ethereum/runs/115974666180),
publisher App ID `5308912`, conclusion `neutral`, at
`metalogiclabs/go-ethereum#21@1c6e656e55b82819f36b0e9a6ea38809ce61b40b`.
It explicitly separates external YAML research evidence from its Ethereum carrier.
The branch README's earlier undeployed/unobserved narrative is stale relative
to these later implementations and readbacks.

There is no generic Lean receipt consumer in this path:

- `native-receipt-bridge.mjs` requires
  `metalogic.real-external-pr-native-evidence.v1`, contributor native test
  methods, red-base/green-head results, full-suite counts and reviewed source/run
  policy. Lean proof receipts do not satisfy that semantic contract.
- `external-native-receipt.mjs` hardcodes the YAML research report, source
  subject, carrier manifest, runs and archive pins. It rechecks metadata rather
  than rerunning native Go tests.
- Open PR168 at `1b71a5ceafe64c2ebf9045425ec6415b3b065dc9` adds two hardcoded
  source-specific decision readers. Its `reclose` maps independent decisions
  over a bounded list; it is not a general theorem dependency engine.
  [Run 38644773386](https://github.com/metalogiclabs/mathgraph/actions/runs/38644773386)
  qualifies smoke and inherited tests, not the original native experiments.

The local integration demonstration in `mathgraph_integration.py` consumes
already qualified complete engine results using the pinned main resolver. It
requires externally supplied evidence and export identities; the CLI can also
require equality with an independently supplied exact result-byte digest. It
does not validate engine HMACs, rerun Lean, authenticate a publisher or install a
production Check profile. Every admitted claim has an exact export, environment
and obligation scope. Checked-this-run and reused-previous-evidence origins stay
visible. Its extra downstream node is an explicitly declared support-projection
conformance case, not an automatically extracted Lean proof dependency. The
single-admission withdrawal is hypothetical, not an observed upstream revocation.

## Verification and limitations

Exact PR168 code extracted outside the checkout passed all **92 Node tests**
across 14 test files. Main's warrant, graph semantics, Resolve publication and
semantic consumer tests passed **69 tests plus 52 subtests**. Separate
`python -I -S` historical replay ran twice with identical output SHA-256
`8c7b30e1eb2a24d2960e170d36652ca95aa71b41075f673abe394e154ae66668`,
matching the workflow pin: three documentary supports stale, three theorem
truths unknown and the JPL control warranted without original Lean rerun.

The broader local attempt on Python 3.12.14/pytest 9.0.3 yielded **84 passed,
72 subtests passed, one failure and 19 setup errors**. The failure is
`conformance/protocol_v1/test_consumer.py::test_normalizes_nesting_limit_through_api`:
malformed input is rejected as `MISSING_FIELD` rather than expected
`INVALID_JSON`; CI pins Python 3.11. The setup errors require unavailable original
source ZIP fixtures. Original archives/logs redirect to Azure blob storage,
which the environment refused. Their GitHub metadata, original run identities
and archive digests were readable; no local original Lean replay is claimed.

Historical main checks are corroborated by
[public evidence 38314180909](https://github.com/metalogiclabs/mathgraph/actions/runs/38314180909),
[living warrants 38314173728](https://github.com/metalogiclabs/mathgraph/actions/runs/38314173728)
and [network-denied Resolve replay 38314179490](https://github.com/metalogiclabs/mathgraph/actions/runs/38314179490),
all at `61ef2879120e1c9e54d11368196d69e47ae437df`.
Relevant implementations and conformance files are unchanged at audited main.
Prior [RealityGraph replay 38025236380](https://github.com/heathsanchez/realitygraph/actions/runs/38025236380)
is implementation-independent under the same owner, not an independently owned
institution and not a rerun of JPL's original proof.

The warranted new compiler work is conservative selection and reuse of checking
obligations under explicit dependency/environment validity. Existing MathGraph
closure should be reused, not reimplemented. Arbitrary Lean source dependency
completeness, a machine-checked refinement proof of the adapter, continuous
freshness, a generic production Lean Check binder and universal correctness
remain unestablished.
