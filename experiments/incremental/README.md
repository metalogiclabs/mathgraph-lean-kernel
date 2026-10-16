# Incremental independent Lean checking

This prototype extends the existing MathGraph/Flash checker. Its low-level Rust
entrypoint checks a selected set of genuine exported Lean declarations; the
Python adapter establishes which omitted obligations retain applicable prior
acceptance evidence. No inference, conversion or reduction rule is changed.

The implemented reuse rule and its explicit assumptions are in [design.md](design.md).
[reconstruction.md](reconstruction.md), [kernel-audit.md](kernel-audit.md), and
[mathgraph-audit.md](mathgraph-audit.md) preserve the prior MathGraph lineage.

The optional [native identity path](native-qualification.md) uses the existing
Rust export parser to accelerate the same adapter. Add
`--identity-backend native --indexer target/release/export-index` to both the
initial and changed verification commands below. Use `differential` in place
of `native` to compare complete Python and Rust identities before admission.
The indexer executable is captured and authenticated as provenance; changing
backends or indexer bytes invalidates incompatible prior evidence. Python
remains the default. [Measured native results](results/native-qualified/summary.md)
distinguish adapter acceleration from the still-unmet direct-Rust timing target.

## Reproduce qualification from a clean Linux x86_64 checkout

```sh
bash experiments/incremental/setup.sh
export PATH="$HOME/.elan/bin:$HOME/.cargo/bin:$PATH"
python3 -m unittest discover -s experiments/incremental -p 'test_*.py' -v
cargo +1.95.0 test --locked --lib
python3 experiments/incremental/build_workloads.py --out results/workloads
python3 experiments/incremental/qualify.py \
  --workloads results/workloads --out results/qualification \
  --authority-dir /tmp/mathgraph-private-authority \
  --repetitions 3 --optional-kernels
```

Use a fresh output and authority directory for each qualification. The installer
pins Lean 4.35.0 (including bundled `leanexport`, C++ kernels and other checkers),
Rust 1.95.0, exporter format, source bytes and base kernel. The final workflow
records its exact checkout SHA. This experiment neither submits to Lean Arena
nor changes protected branches.

The workload exports real `Std.HashMap.getElem?_insert` and
`Std.HashMap.getElem?_erase` transitive dependencies, alongside source-controlled
edits that expose leaf, transitive and unrelated changes. It contains thousands
of actual declarations. Invalid-proof and standard-axiom mutations occur at the
export boundary because source elaboration correctly rejects invalid proofs.
Pinned upstream source is supplied by the Lean release, not a moving checkout.

`summary.json`, `summary.md`, exact exports, source edits, every command's exit
status/stdout/stderr/CPU/wall/peak-RSS, per-obligation engine decisions, signed
records and independent-kernel results are retained. Failed or timed-out kernel
runs are reported separately. Optional checker disagreement cannot silently
become agreement. The baseline and changed inputs are independently checked by
both bundled official C++ kernel variants on the same exact NDJSON.

## Direct interface and cold restart

```sh
python3 experiments/incremental/engine.py --init-key /tmp/private-issuer.key
python3 experiments/incremental/engine.py \
  --export results/workloads/baseline/export.ndjson \
  --checker target/release/check-selected --cache /tmp/reuse-cache \
  --authority-key /tmp/private-issuer.key --output /tmp/first.json
# Supply the first result's exact evidence_id as PREVIOUS_EVIDENCE.
python3 experiments/incremental/engine.py \
  --export results/workloads/early-definition/export.ndjson \
  --checker target/release/check-selected --cache /tmp/reuse-cache \
  --authority-key /tmp/private-issuer.key --previous "$PREVIOUS_EVIDENCE" \
  --output /tmp/changed.json
```

Every invocation is a fresh process. Restart needs the authority key, immutable
record, exact previous export blob, and the pinned checker/adapter bytes. The
key belongs outside the untrusted cache, is created with mode0600 and is never
published by the workflow. Public artifacts are independently replayed by
performing a new full check under a new local issuer, then reusing that evidence;
they do not require a historical secret or unpublished agent state. Externally
pinned record hashes can also establish exact public artifact identity, but
cannot alone establish that a kernel accepted the input.

A cache corruption, foreign issuer, toolchain/configuration/policy mismatch or
missing evidence refuses reuse and falls back to full checking. Corrupt export
blobs are quarantined before restoration from freshly checked bytes. No record
is issued if any required obligation rejects, parsing fails, an input is
unsupported or a timeout occurs. A rejection does not claim that all scheduled
obligations ran: completed work is UNKNOWN when the checker stops early.

`verify_incremental(previous_evidence, changed_development, verifier_policy)`
returns `VERIFIED_NEW` and `VERIFIED_REUSED` per obligation, separate `INVALIDATED`
events, aggregate `REJECTED` or `UNKNOWN`, dependency fingerprints, exact evidence
origins and tool provenance. Reused obligations remain previously warranted
evidence whose applicability was re-established, rather than fresh checks.

## MathGraph and upstream integration boundary

`mathgraph_integration.py` feeds caller-qualified results into the existing
pinned MathGraph typed warrant resolver. It preserves exact environment and
obligation scopes, checked-versus-reused origins, historical evidence and
withdrawal behavior. Independent full-oracle qualification is required before
admission. The production neutral MathGraph Check binder has a different,
specific native-test schema; this experiment does not pretend to publish Lean
results through that binder. A future binder can use these scoped receipts
without changing the kernel adapter or the warrant engine.

Lean 4.35's `lake check --from-export` already accepts the same format. This
prototype's selected checker can become a modular incremental checker adapter;
no Lean core patch is needed. `lake check --paranoid` is a fresh independent
comparison policy, not the reuse predicate.

## What the evidence can establish

Passing qualification warrants exact-export agreement and work reduction on
this pinned finite test set, authenticated restart and fail-closed controls.
The theorem in `BoundedReuse.lean` has no axioms but explicitly assumes complete
semantic dependencies, locality, fingerprint adequacy and deterministic checks.
It does not prove the Python extractor, Rust implementation or whole pipeline.
The trusted issuer, trusted adapter code and selected kernel implementation
remain explicit assumptions.

Report both raw full-kernel cost and complete adapter cost. The current changed
export index scans the whole file; dependency-local checking work does not make
parsing or indexing proportional to the edit. Wall speedup for changed inputs
must be measured, not inferred from reused counts. No Mathlib-scale performance
or general semantic-equivalence claim follows from this workload.
