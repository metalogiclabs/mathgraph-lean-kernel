# Accepted predecessor continuation

`RevisionChainSession` extends the qualified producer-delta adapter. It retains
the latest accepted Lean environment/exporter, native identity graph and genuine
Rust parser across successive revisions. Default `DeltaSession` and native CLI
behavior remain one-shot. This is a research interface over the existing
authority and applicability predicate.

```python
from revision_chain import RevisionChainSession

with RevisionChainSession(root=cache_directory, workloads=pinned_workloads,
        producer=producer, checker=selected_checker, indexer=export_index,
        index_session=index_session, retained_checker=retained_checker,
        authority_key=private_issuer_key) as session:
    session.start()  # new epoch: genuinely check the pinned genesis export
    result = session.apply(complete_source_directory, checked_source_patch,
                           actual_expected_changed_names)
    assert result['status'] == 'VERIFIED', result
    # Persist this head outside the untrusted cache only after VERIFIED.
    expected_head = result['revision_chain']['head_id']

with RevisionChainSession(...) as restarted:
    restarted.start(expected_head=expected_head)
```

Every source capture reads the complete bounded six-file application universe.
The producer compares the actual current environment with its predecessor;
reported names are assertions. Existing fixed-import, schedule, kind, metadata,
global-assumption and toolchain restrictions still apply. The retained graph
uses its existing conservative full-index fallback after topology changes.
Every changed DAG row goes through the actual Rust parser, even with no selected
obligations. Selected obligations use the unchanged genuine checker.

Acceptance promotes the source capture, exact sealed export bytes, layout,
authenticated index, receipt and chain head together only after checking and
content-addressed persistence. Any failure poisons all live processes. A sealed
failed input remains available solely for independent rejection replay until
`close()`. A receipt orphaned by later persistence failure records genuine
historical checking, but does not promote an accepted chain head.

The new HMAC domain binds each head to its immediate parent head/evidence,
revision, complete source-capture identity, exact export/delta identities and
versioned producer policy. The existing HMAC key/authority and verifier policy
remain in use. Cold recovery authenticates every referenced object and rebuilds
the producer/exporter history, index and selected checking from genesis, using
the original authenticated envelopes after independently reproducing their
source/delta inputs. Timing fields and private output paths are not regenerated
as historical identities. An expected head supplied by the caller is required
on restart: HMAC authenticates a historical prefix, not its latestness. There is
no external monotonic service or generic rollback guarantee.

Restoring source and semantic identities need not restore the genesis export
SHA: retained append-only DAG rows may remain unused. Old evidence is historical;
a rejected or UNKNOWN current source does not inherit current acceptance.

Reproduce the real-workload smoke and adversarial checks:

```sh
python3 experiments/incremental/test_revision_chain.py \
  --workloads artifacts/workloads --producer artifacts/delta-build/delta-producer \
  --binaries target/release --output artifacts/revision-chain-tests-original
python3 experiments/incremental/test_revision_chain_controls.py \
  --workloads artifacts/workloads --producer artifacts/delta-build/delta-producer \
  --binaries target/release --output artifacts/revision-chain-controls-original
```

The exact-source workflow `incremental-revision-chain.yml` also repeats these
on the 11,653-obligation profile and preserves the earlier qualification suites.
Its lifecycle benchmark uses five actual forty-revision sequences per profile,
with fresh full Rust checking on every identical sealed input, independent full
index/partition comparison at each step, representative Python/C++/paranoid
oracles, authenticated receipts and a cold replay of the final forty-step head.
The full benchmark CLI is in that workflow; `--smoke --repetitions 1 --cycles 1`
permits a smaller correctness run without a qualification claim.

Economics charge constructor/start, every complete producer-to-persistence API
call and supported close. The primary wall measurement runs a separate,
uninterrupted production sequence, then audits its exact input identities and
receipts against the independently checked sequence. Its direct comparator runs
genesis plus every changed input through a fresh Rust process, uninterrupted;
the two arms alternate order across five pairs. Input materialization for that
direct comparator occurs before timing, making it the favorable raw-checker
baseline. Source production and receipt persistence remain inside incremental
timing. Observed API component sums from the interleaved qualification sequence,
its oracle-inclusive elapsed interval, and cold recovery are separate scopes.
No uninterrupted wall-time claim is inferred from a component sum. Procfs CPU
ticks and post-phase memory observations have their documented scope.

The pipeline remains linear in complete export materialization/hashing, some
index/receipt scans and retained-name construction. Native graph promotion also
copies the complete index. Cold replay grows with accepted history. This is not
asymptotically change-proportional total verification. The source/export/parser/
identity bridge remains an executable assumption tested by differential and
negative controls; no whole-pipeline formal verification is claimed.
