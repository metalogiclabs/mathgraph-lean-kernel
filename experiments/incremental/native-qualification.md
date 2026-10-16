# Native identity-index qualification

This experiment replaces the Python identity/dependency scan with a release
Rust indexer while preserving the existing authenticated reuse rule. Correctness
and economic value are separate results: equal indexes and fewer kernel
obligations do not establish that the complete incremental process is faster
than a direct full check.

The original implementation is pinned to
`9ac04033b51703fb135ec3c28621d44b183944fe`. Its `check-selected` and `sokonanoda`
binaries must be compiled from that exact source in an isolated worktree and
copied to `artifacts/native-baseline-bin/` before benchmarking. Rebuilding current
source and calling it the original baseline is not a valid comparison. The
workflow retains the resolved source ref, build log and binary SHA-256 values.
The existing MathGraph consumer remains pinned to
`cf359686c74549a132c7a651cd7aabc7c1a870fe`.

## Fixed inputs and authority boundary

`pins.json`, `workload/` and `build_workloads.py` define the unchanged source and
export matrix. Lean remains `leanprover/lean4:v4.35.0`, commit
`eb6cafb7290e8bd5f2937522d8d804f58f02bafc`; the export format remains 3.1.0 and
Rust remains 1.95.0. The generator verifies source digests, release executable
digests and the exact export digest for every case. Genuine source builds export
the existing Std HashMap dependency cone, with 3,436 flattened obligations from
3,145 top-level declaration records in the pinned baseline.

| Case | Construction and required boundary |
| --- | --- |
| `baseline` | Unchanged genuine source/export; full acceptance and identical-export reuse. |
| `early-definition` | Source Nat literal 17 to 23; transitive invalidation. |
| `unrelated-definition` | Source unrelated definition edit; unaffected obligations retain applicable evidence. |
| `theorem-leaf` | Source proof edit; changed proof identity is checked. |
| `type-change` | Source declaration type edit; dependent identity is reconsidered. |
| `invalid-proof` | Export-boundary invalid theorem value; real kernels reject. |
| `axiom-type` | Export-boundary standard axiom type mutation; policy/kernel rejection. |
| `toolchain-metadata` | Export metadata drift; refuses old reuse and performs fresh checking. |
| `malformed-unused-dag` | Export-boundary unused expression with missing references; no acceptance evidence. |
| `malformed-unused-typed-node` | Export-boundary ill-typed unused node; the real Rust parser rejects even with no selected obligations. |

The native indexer changes identity extraction, not Lean inference, conversion,
reduction or axiom policy. Dependency hashes identify bytes and conservative
semantic structure; acceptance still comes from real kernel execution or
authenticated prior acceptance whose applicability is re-established. The
issuer key stays outside published caches and artifacts. The existing locality,
dependency-completeness, fingerprint and trusted-adapter assumptions still apply;
the bounded theorem does not prove the new Rust indexer.

## Interfaces and fail-closed behavior

Build the native executable with the existing pinned setup:

```sh
bash experiments/incremental/setup.sh
```

`target/release/export-index CONFIG.json` accepts the same configuration as
`qualify_native.configuration(export)`, including the current axiom and
extension policy:

```json
{
  "export_file_path": "/absolute/path/export.ndjson",
  "use_stdin": false,
  "permitted_axioms": ["propext", "Classical.choice", "Quot.sound"],
  "unpermitted_axiom_hard_error": true,
  "num_threads": 1,
  "nat_extension": true,
  "string_extension": true,
  "print_success_message": true
}
```

Successful stdout is the
exact JSON value returned by Python `engine.make_index` on the same bytes,
including metadata, ordered declaration identities, static dependencies,
fingerprints, visibility/schedule identity and mutual-inductive group identity.
JSON object key order is immaterial; array order, field types and hash values
must agree. A native rejection uses a structured diagnostic and nonzero exit,
never a partial successful index.

The engine and original qualification harness expose
`--identity-backend python|native|differential` and `--indexer PATH`. Python
retains the reference extractor. Native requests the native index. Differential
compares Python and native results before using identity data. A recognized,
structured native refusal falls back through Python extraction and the actual
selected-kernel parser when extraction succeeds. A successful native index that
disagrees with Python, a crash, malformed protocol or timeout returns UNKNOWN
without a new receipt. None of these cases authorizes reuse. An unused
malformed record cannot disappear merely because the selected obligation set is
empty. Rejection or UNKNOWN issues no new acceptance record.

## Correctness qualification

```sh
export PATH="$HOME/.cargo/bin:$HOME/.elan/bin:$PATH"
cargo +1.95.0 test --release --locked
python3 experiments/incremental/test_predicate.py
python3 experiments/incremental/test_native_identity.py
python3 experiments/incremental/test_native_adapter.py --checker target/release/check-selected
python3 experiments/incremental/build_workloads.py --out artifacts/workloads
task_authority="$(mktemp -d)" # Keep outside artifacts, for independent replay.
python3 experiments/incremental/qualify_native.py \
  --workloads artifacts/workloads --out artifacts/native-qualification \
  --checker target/release/check-selected \
  --full-checker target/release/sokonanoda \
  --indexer target/release/export-index --authority-dir "$task_authority"
python3 experiments/incremental/replay_native.py \
  --qualification artifacts/native-qualification/original-qualification \
  --workloads artifacts/workloads \
  --authority-key "$task_authority/original/issuer.key" \
  --checker target/release/sokonanoda --indexer target/release/export-index \
  --reference experiments/incremental/results/local-qualified.json \
  --out artifacts/native-independent-replay
```

The release test run includes the original 47 checker tests, and the predicate
suite preserves the original ten adversarial identity tests. Native
qualification compares complete Python/native indexes for all supported pinned
exports and checks rejection/fallback for negative inputs. It compares backend
outcomes, checked/reused partitions, selected obligations, invalidation and
dependency decisions; different signing authorities or process resources are
not semantic disagreements. It retains every invocation's configuration,
stdout, stderr, exit status and resource record, including failing controls.

By default `qualify_native.py` also runs the original three-repeat, ten-variant
197-gate qualification with the native backend and mandatory independent normal
and paranoid C++ kernels. That output lives in
`artifacts/native-qualification/original-qualification/`. Existing authenticated
restart, cache corruption, missing evidence, foreign authority, policy/toolchain
drift, checker drift and no-evidence-on-failure controls remain required.
Optional checker failures retain their actual classification and raw logs.

CI also runs `replay_native.py` before benchmarking. It independently checks the
original gate names against `results/local-qualified.json`, authenticates the
retained acceptance records, and launches 21 fresh full-oracle processes. The
qualification authority lives under `$RUNNER_TEMP/native-index-authority`,
outside uploaded artifacts; replay receives the original issuer key path.

The existing integration harness consumes that original qualification output:

```sh
python3 experiments/incremental/qualify_integration.py \
  --qualification artifacts/native-qualification/original-qualification \
  --mathgraph /path/to/mathgraph-at-cf359686c74549a132c7a651cd7aabc7c1a870fe \
  --out artifacts/mathgraph-integration
```

This checks the existing typed warrant resolver's scoped checked/reused origins
and withdrawal behavior. It does not turn a matching index into kernel
acceptance or establish a production MathGraph Lean binder.

## Complete-process economic comparison

```sh
python3 experiments/incremental/benchmark_native.py \
  --workloads artifacts/workloads --out artifacts/native-benchmark \
  --baseline-bin artifacts/native-baseline-bin \
  --baseline-ref 9ac04033b51703fb135ec3c28621d44b183944fe \
  --repetitions 5
```

The benchmark compares original and current direct full checking, Python
identity extraction and the complete native incremental adapter. Direct full
checking means invoking the real full-checker executable on the same export,
without Python adapter/cache overhead. Original baseline binaries come from the
separately compiled pinned revision. All five measured binaries are captured
under `captured-tools/` before timing, with their exact hashes. The current
engine is preserved under `source-snapshot/`, and a final source-stability gate
checks that its live bytes did not change during measurement. The original
engine is copied verbatim from the pinned Git revision under `baseline-source/`.

Every timed sample is a fresh whole process. Wall time and child-inclusive CPU
time cover startup, parsing/indexing, old-evidence validation,
selected kernel work, signing and persistence for the incremental command.
Index-only and selected-kernel phase timings may help explain cost, but cannot
replace whole-process measurements. Each repetition independently seeds one
baseline cache per backend; every incremental measurement names that original
seed. A fixed recorded random seed shuffles measurement order within each
repetition. Retained seeds and execution order make pairing reviewable. Seed cost is
reported separately from a warm incremental verification and must be included
when making lifecycle claims.

The benchmark retains raw `wait4` RSS highwaters. They can include the large
Python launcher's inherited pre-exec RSS and cannot support memory-saving claims.
The separate `profile_native_phases.py` diagnostic samples post-exec parent and
descendant RSS by phase. Its sampled sums can count shared pages twice and are
not exact aggregate peaks; its instrumented timings are excluded from economics.

The primary economic criterion is strict: the robust median complete native
incremental wall time must be lower than direct raw full checking for **both**
`early-definition` and `unrelated-definition`. Each case must also win a strict
majority of repetition pairs, and the deterministic paired-bootstrap 95% upper
ratio-of-medians bound must be below one. This finite-run stability check does
not establish cross-host performance. Report each case independently,
alongside all repetitions, CPU/RSS and the paired execution order. A fast
unchanged-export case, lower checking-phase time, higher reuse count, or a win
against the slower Python adapter does not satisfy this criterion. A failed
economic gate is a retained negative result, even when correctness passes.
Correctness with a failed economic gate reports `NO_SPEEDUP` and exits zero;
`--require-speedup` additionally makes the economic gate control the exit code.

The workflow at
`.github/workflows/incremental-native-index.yml` runs only for pushes to
`research/incremental-native-index-20261016` and manual dispatch, uses pinned
checkout/upload actions, and always uploads `artifacts/`, including preserved
baseline binaries, source/export inputs, summaries and raw process logs. The
MathGraph integration step can still run after an economic failure when
correctness qualification succeeded. Local results and CI results must each
name their actual source SHA, binary hashes and artifact provenance; neither a
workflow definition nor prior Python qualification constitutes a new native
success claim.
