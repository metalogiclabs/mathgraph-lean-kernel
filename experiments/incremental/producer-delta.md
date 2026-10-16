# Authenticated producer deltas

This bounded experiment continues qualified source `c5ab12699338aa57b7e9d48b15d4a7409e453c7b`.
Its objective is a complete warm changed-input transaction faster than direct
fresh Rust checking. Economic results require the exact-source qualification;
probe timings and the workflow definition alone do not establish success.

## Implemented boundary

`DeltaProducer.lean` loads the pinned Std import once and owns its immutable
imported environment. Every update captures all six application inputs, permits
an exact declared patch in one of the three editable module bodies, and refuses
configuration, toolchain or import-root changes. It re-elaborates all seven local
declarations against the same imported environment and compares every local
`ConstantInfo`, including generated declarations and additions/deletions. The
caller-reported changed names must equal this complete comparison. The imported
constant map must retain its identity. Filenames, timestamps and changed-name
hints never authorize reuse.

The producer retains LeanExport's actual expression/name/level tables and emits
new DAG rows plus replacements for existing simple declarations. The original
baseline and changed fresh exports reproduce the previous pinned bytes exactly.
An optional expanded profile adds 5,309 deterministic existing Std HashMap roots:
11,653 declarations and about 64 MB, versus the original 3,436 declarations and
about 16 MB. Every expanded export is separately pinned to ordinary bundled
`leanexport` on the original compiled workload, with the same explicit roots.

The native `index-session` initializes through the existing real Rust parser,
retains typed identities, and applies only appended DAG rows and same-name,
same-kind simple declaration replacements. It reuses the existing complete
declaration SCC/dependency routine. It never supplies acceptance authority.

The Python owner authenticates a producer transition in a separate HMAC domain,
binding the accepted baseline, complete captured source root, delta bytes,
producer/indexer/checker versions, profile and verifier policy. Genesis and
transition records cannot be used as accepted verification receipts. The
existing issuer key and canonical signing algorithm remain unchanged.

`engine.reuse_decisions` is the original predicate factored without changing its
rules. Its tests compare 4,096 combinations with the original c5ab126 predicate.
The complete current export is reconstructed into a Linux sealed memfd: baseline
DAG, appended DAG, original declaration order with replacements. The actual
selected checker always parses that complete input, including when selection is
empty. Only a successful actual check permits the normal HMAC acceptance record.

New durable storage contains the changed export rows, producer attestation,
representation manifest and acceptance receipt; the baseline export is retained
once. The acceptance receipt still contains the complete typed index. No full
changed export is rewritten to durable verification storage. A full current
input is nevertheless materialized in RAM for the unchanged kernel interface.

Cold restart reauthenticates baseline/genesis/tool policy, reconstructs source
and index state from exact pinned baseline bytes, authenticates every referenced
object and independently replays the transition. A checksum-only session file
or reconstructed object cannot establish authority. This is replay of an exact
historical owned representation, not a claim that an external mutable source
tree has remained unchanged since capture.

## Qualification and economics

Build the same pinned tools and actual inputs as the original qualification:

```sh
bash experiments/incremental/setup.sh
export PATH="$HOME/.cargo/bin:$HOME/.elan/bin:$PATH"
cargo +1.95.0 build --release --locked --bin index-session
bash experiments/incremental/build_delta_producer.sh artifacts/delta-build
python3 experiments/incremental/build_workloads.py --out artifacts/workloads
python3 experiments/incremental/build_delta_workloads.py \
  --workloads artifacts/workloads --out artifacts/delta-expanded-workloads \
  --producer artifacts/delta-build/delta-producer
mkdir -p /tmp/mathgraph-delta-authority
python3 experiments/incremental/engine.py --init-key /tmp/mathgraph-delta-authority/issuer.key
python3 experiments/incremental/qualify_delta.py \
  --workloads artifacts/delta-expanded-workloads \
  --producer artifacts/delta-build/delta-producer \
  --checker target/release/check-selected --indexer target/release/export-index \
  --index-session target/release/index-session --full-checker target/release/sokonanoda \
  --authority-key /tmp/mathgraph-delta-authority/issuer.key \
  --out artifacts/delta-expanded-qualification --repetitions 5
```

Use new output/key directories for a clean qualification. Issuer keys must stay
outside published artifacts. The workflow preserves all original 197 gates,
native differential/replay controls and old benchmark correctness checks, then
runs both producer profiles. Missing, partial, false or wrong-source reports
fail the workflow. It publishes full and compact evidence archives even on
failure.

Each warm timing includes complete source capture, real Lean re-elaboration and
export, producer authentication, retained identity update, baseline validation,
full materialization/hash, actual checking, signing and durable persistence.
The direct fresh Rust process reads the identical live sealed bytes. Pair order
is fixed update-then-direct and disclosed; the direct comparator runs before
fresh index oracles. OS file cache is warm. Profiles and hosts are not pooled.

Initial baseline verification, binary capture and resident-session construction
are separately timed; they are excluded from warm updates. Cold reconstruction
and lifecycle costs must be reported separately. CPU includes the still-running
producer/index processes using procfs clock ticks, as well as adapter/completed
children. Memory samples are post-phase process RSS and cumulative highwaters;
they are not exact phase peaks or aggregate savings.

The prespecified early-edit gate requires a lower median than direct fresh Rust,
a strict majority of five paired wins, and a paired-bootstrap 95% upper ratio
bound below one. Correctness with no economic win is a retained `NO_SPEEDUP`,
not success. Positive tests compare against original Python and fresh native
indexes and independent full Rust/C++/paranoid checks. Controls include forged
deltas, producer-bug invalid proofs/axioms/unused nodes, outside-region sources,
environment/version drift, foreign issuers, corrupted objects and cold restart.
Unexpected timeouts or protocol errors cannot masquerade as a passed refusal.

## Scope and remaining cost

The trusted applicability boundary gains the source-owning producer and delta
decoder. Their source/binary hashes are bound to the issuer's evidence. The
kernel, verifier policy, reuse predicate and downstream MathGraph resolver are
unchanged. The bounded Lean theorem does not prove this executable bridge.
FLASH/Nucleus lineage and actual qualification limits are in
[delta-lineage.md](delta-lineage.md); neither supplied an existing Lean delta
protocol or a transferable checker verdict.

Fresh ordinary-export identity parity is qualified for the recorded finite
edits. General simple source replacements can change a fresh root export's
dependency closure or traversal order; universal parity is not claimed. The
supported representation retains the old published ordered environment, and
conservatively refuses new declarations, kind changes and complex mutations.

This is not asymptotically change-proportional verification. Producer hash-table
copy-on-write can copy retained capacity; declaration SCC reclosure and result
serialization visit all declarations; baseline authentication, full-byte hashing,
materialization, parser restoration and complete-index receipts remain O(N).
The experiment removes full expression-DAG identity reconstruction and durable
full-export rewriting while preserving these explicit remaining costs.
