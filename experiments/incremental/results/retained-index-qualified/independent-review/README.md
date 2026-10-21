These frozen reviewers use standard-library Python and a Git checkout containing the tested source and its history. They import no producer, checker, engine or qualification controller code. The two legacy dependencies are independent review code and are verified by exact SHA256 before import. Keep all three Python files together; explicit --legacy-helper and --delta-helper overrides are supported. No unpublished /tmp dependency is required.

The preserved diagnostic report is **DIAGNOSTIC_ONLY_NOT_QUALIFICATION**, with passed=false: 4,597 structural checks and 14 fail-closed reviewer falsifiers over local diagnostic fixtures. It does not qualify CI38961520032 or promote undersampled economics. independent-review-preparation.json records the frozen hashes and pending-CI state.

After downloading the actual compact artifact and actual provider/run/jobs metadata, run from this directory:

```sh
python3 retained-ci-review.py \
  --repo /path/to/mathgraph-lean-kernel \
  --source ef434eb2477fb64d7fd90fdf23f55bd0b35a0243 \
  --run 38961520032 \
  --job 117177490277 \
  --zip /path/to/downloaded-compact-artifact.zip \
  --metadata /path/to/provider-artifacts.json \
  --run-json /path/to/final-run.json \
  --jobs-json /path/to/final-jobs.json \
  --falsifiers \
  --out /path/to/independent-actual-ci-review.json
```

--metadata accepts the provider compact artifact object, an artifact wrapper, or an artifacts listing containing exactly one incremental-retained-index-summaries-ef434eb2477fb64d7fd90fdf23f55bd0b35a0243 object. Provider name/source/run/bytes/SHA256 must match the downloaded ZIP. --run-json is the actual final Actions run object; --jobs-json is its actual job object or jobs listing. Supply both for run/job/required-step checks. All captured source hashes are checked against Git bytes at the explicit tested commit.

Strict actual review requires the complete181-gate retained report (20 paired samples, three arms), retained legacy suites and two producer profiles,26 independent fixtures, four seven-repetition isolated microbenchmarks,20 storage pairs and44 intended-cause controls. It recomputes medians, paired wins, bootstrap intervals, counters/scaling and lifecycle component sums. Legitimate NO_SPEEDUP findings pass correctness review.

PASS_WITH_STATED_LIMITS checks archive/provider integrity, source and executable pins/stability logs, projections and arithmetic. Compact archives omit full sample/index/cache witnesses and private issuer keys. This reviewer does not reread omitted witnesses, reauthenticate historical HMACs or execute kernels. Separate actual replay evidence is required for those claims. Isolated core, whole finish/cleanup, index roundtrip, warm apply, setup and shutdown retain distinct scopes. RSS is sampled and VmHWM cumulative, not exact phase peaks or memory savings. Sparse capsules remain storage representations, never new acceptance evidence.

Verify staged bytes with `sha256sum --check SHA256SUMS`. Actual CI artifact review remains pending; this preparation asserts no actual CI result.
