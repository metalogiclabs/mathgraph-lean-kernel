# Incremental external Lean checking: bounded executable contract

Objective: agreement with a fresh independent check on the exact pinned export,
with strictly fewer checked obligations for qualifying edits. Existing FLASH
warrant reclosure is retained as downstream authority; this adapter supplies the
missing kernel-bound declaration evidence and applicability predicate. It is not
a replacement warrant scheduler.

Base: MathGraph/Flash 78c7502bac8a5ba000057b3f083bc0595ac65750. The successful
409-case qualification is Actions 35596011019. The keyed-closure optimization
9588f879 has the same src tree and is intra-invocation only. The older
88cc241 incremental-ai-loop already supplies a caller-trusted prefix-check API,
but no persisted admission proof. We extend that checking operation with a
selected-obligation adapter; no kernel inference or reduction rule changes.

## Validity boundary

Evidence is issued only after checking succeeds. A separate authority key signs
immutable, content-addressed manifests. The key is outside the untrusted cache;
the caller must trust that issuer and retain the expected evidence identifier.
A hash establishes byte identity; it does not establish logical acceptance.
Cache files, signatures, snapshots, tool binaries and policy are validated before
any reuse. Key compromise and a malicious issuer are outside this boundary.

An identical export with identical policy/tool provenance can reuse every
previously verified obligation. Otherwise exact verified prefix reuse is
permitted only with stable global assumptions. For dependency-local reuse of
simple declarations (axiom, definition, opaque, theorem), require:

1. Identical declaration name and complete structural contents (typed name,
   universe parameters, type, value, safety and reduction metadata), independent
   of serialization interning indices.
2. Identical ordered declaration-name schedule; this conservatively preserves
   lookup cutoffs, mutual block structure and absence/future visibility.
3. Identical full transitive syntactic and metadata dependency fingerprints.
   These include constant references, projection type names, inductive families,
   constructors, recursors, recursor RHSs, types and values. Every name in a
   complex declaration is conservatively a dependency.
4. Every implicit builtin NameCache root and its entire dependency closure is
   identical. Pin presence in *all parsed names*, not just declarations. This
   covers Nat/String/Char/List/Bool and quotient environment-sensitive rules.
5. Exact Lean/exporter/format metadata, checker executable, adapter source,
   configuration, issuer and verification policy identity.

Changed complex obligations are always freshly checked. Complex obligations
outside an exact verified prefix are also freshly checked. Dependency cycles are hashed as complete strongly connected components;
missing names are preserved as negative lookup facts under the same name
schedule. Original mutual-inductive block boundaries are globally pinned. All declarations in the resulting
environment must be either checked in this invocation or admitted by this
predicate; no unchecked caller-supplied list is an acceptance certificate.
Any check failure prevents issuance for the entire changed environment.

This deliberately over-invalidates: even opaque proof dependencies include the
proof value, and builtin changes revoke all simple reuse. Source paths and
unchanged source text are never acceptance evidence.

## Independent boundary and experiments

The official Lean 4.35.0 C++ kernel (`leanchecker --from-export`) checks the exact
NDJSON independently. `lake check --from-export --paranoid` adds other bundled
kernels where practical; statuses remain separate. An invalid proof is injected
at the export boundary because the elaborator correctly refuses invalid source.

Qualification compares fresh and incremental outcomes, counts actual selected
kernel calls, cold restarts, authenticates corruption controls, changes proof,
definition, type/axiom and policy assumptions, and restores dependencies. Timings
include export, parsing/identity, cache validation, checking, CPU and memory.
A bounded Lean model, if supplied, proves only the abstract reuse rule under an
explicit dependency-congruence assumption. The NDJSON dependency extractor and
its connection to the real kernel are audited/tested executable assumptions,
not formally verified by that model.
