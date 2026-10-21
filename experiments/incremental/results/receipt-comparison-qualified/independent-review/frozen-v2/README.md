# Independent receipt-comparison evidence review

Frozen target source: `5dfe38b01ca7b1c67f70be4ffb2479978049239e`.
Target workflow run: `39581949051`, `incremental-receipt-comparison.yml`.
The job ID, artifact ID, completed provider metadata and archive digest must come
from that actual completed run. Preparation and local one-pair diagnostics are
not CI qualification.

The reviewer is portable and self-contained: Python 3.10+ standard library,
Git, and a local repository containing the exact target commit. It imports no
incremental engine, controller, benchmark, or old reviewer dependency. Keep
the test file beside the reviewer to replay its synthetic contract tests.

The current reviewer is contract revision2. Exact revision1 bytes and hashes
remain in `frozen-v1/`. `reviewer-v2-red.log` and `reviewer-v2-red-tests.py`
preserve the pre-fix failures for actual cold-baseline projection and an exited
process observation. Warm starts require VERIFIED, full actual checker counts
and the exact setup baseline ID. Cold starts require VERIFIED and
`authenticated_prior_baseline_not_a_new_full_check`, no new counts/checker result,
and that same original baseline ID. Cold accepted receipt and decision parity
remain mandatory. A raw `None` process observation remains absent, never zero.
To replay the preserved RED case, place `reviewer-v2-red-tests.py` beside a copy
of `frozen-v1/review_receipt_comparison.py` in a temporary directory and run:
`python3 reviewer-v2-red-tests.py Contracts.test_actual_cold_baseline_projection_is_prior_authentication Contracts.test_missing_exited_process_observation_is_not_zero`.
Both fail under v1 and pass with the current v2 helper.

```bash
python3 test_review_receipt_comparison.py
python3 review_receipt_comparison.py \
  --repo /absolute/path/to/mathgraph-lean-kernel \
  --source 5dfe38b01ca7b1c67f70be4ffb2479978049239e \
  --run-id 39581949051 --job-id ACTUAL_JOB_ID --artifact-id ACTUAL_ARTIFACT_ID \
  --run /path/to/run.json --jobs /path/to/jobs.json \
  --artifacts /path/to/artifacts.json \
  --archive /path/to/receipt-comparison-summaries.zip \
  --out /path/to/independent-review --falsifiers
```

The archive is CRC/path checked and extracted beneath the output directory.
Its bytes and SHA must match the provider artifact metadata. Run source,
conclusion, job/steps and artifact/run/source identity are required. The helper
binds report/source hashes to exact Git bytes, checks source/binary stability
manifests, original 197/335/719/251 and protected 246/229 minimum gate inventories,
all 21 protected control causes, shadow parser controls, all 20 five-pair cases
(40 actual arms), both policy-mode refusals per profile and all four cold arms.

It independently recomputes warm wall/CPU, selected checking, persistence,
setup+one-apply components and each arm's fresh full Rust comparison, using the
actual reported paired bootstrap seeds. It retains CPU and post-phase process
memory observations without inventing missing-process zeros or peak-memory
savings. It structurally replays eight representative complete witnesses:
baseline export plus delta to exact composite SHA/length; baseline index plus
typed patch against the fresh full native index; the original conservative
prefix/dependency predicate against every complete decision; signed-payload,
receipt/representation/transition content IDs; actual checker configs and raw
output digests targeting the same sealed snapshot.

This audit does not execute kernels, authenticate historical HMACs without
issuer keys, prove the retained parser bridge or comparator, rebuild omitted
executables, or establish a multi-update lifecycle. Nonrepresentative samples
are checked through compact observations and published hashes. Setup+apply
is a component sum excluding shutdown and independent oracles. Total work
still includes complete reconstruction, reuse, materialization and hashing.

`reviewer-falsifier-tests.json` contains 32 synthetic mutations that must refuse
partial/missing/wrong-source reports, timing/count/kernel/policy/authentication
claims, incorrect scopes, cold failure and a wrong cross-mode refusal cause.
The added mutations reject invented cold full-check claims, missing/wrong warm
checks, missing status and foreign baseline evidence. The tests additionally
reject unrelated protected negative-control causes,
duplicate JSON keys and topology-changing patches. `diagnostic-content-review.json`
records only independent local one-pair content replay on real original-profile
records; it is not a five-pair or CI qualification report.
