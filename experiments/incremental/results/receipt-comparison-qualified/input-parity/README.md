# Frozen standalone CI input-parity helper

Prepared and tested before inspecting the new compact CI artifact for source `5dfe38b01ca7b1c67f70be4ffb2479978049239e`. This helper imports no engine, producer, receipt consumer, or kernel. It compares explicit snapshot SHA256 **and integer byte size** to the independently executed74-process replay, whose top-level summary is copied byte-identically as `local-replay-summary.json` and pinned in the helper by SHA256.

Run against the directory containing the extracted compact artifact:

```sh
python compare_inputs.py --ci-root /path/extracted-artifact \
  --local-summary local-replay-summary.json --out /path/ci-input-parity.json
```

The exact expected report locations are:

- `receipt-protected/original/protected-matrix/retained_selected/summary.json`
- `receipt-protected/expanded/protected-matrix/retained_selected/summary.json`
- `receipt-comparison/summary.json`

The checker compares all protected early/unrelated positive snapshots, all four kernel-negative control roles per profile, every canonical/shared warm comparison arm, and both cold-mode snapshots per profile. Hash and byte-size fields are required; a filename, matching count, report success flag, or role name alone cannot create a match. Reported accepted/rejected/zero-parser outcomes, absent negative acceptance, source identity, and no-persisted-acceptance gates are checked separately.

Output separates exact `matches`, `missing`, `mismatched`, and `metadata_errors`. It maps every covered local full/native replay claim to observations. The two local overwrite cases appear only under `extra_local_overwrite_roles`: they are conservative retained-policy refusals with fresh zero-selected parser acceptance, and no equivalent CI kernel-negative fixture is assumed. Protected baseline/theorem-leaf samples are explicitly outside the local74-process kernel replay scope. No economic result or HMAC validity is inferred by this helper.

For a complete expected artifact there are74 CI snapshot observations:22 protected positives, eight protected negatives,40 paired warm arms, and four cold arms. These correspond to12 unique profile/role keys and18 local replay claims after the two overwrite claims are separated. The numerical74 is coincidental; it is not the number of remote kernel invocations. The actual local replay separately executed74 processes.

`test_compare_inputs.py` builds synthetic report shapes with the frozen local hashes; it never fabricates actual CI observations. Eleven tests cover success, hash mismatch despite matching role/count, size mismatch despite matching hash, missing hash/control/report, boolean byte size, source drift, an accepted negative, a missing zero-parser result, cold hash/policy mismatch, conflicting local repeated roles, missing comparison arms, and duplicate repetitions. All passed before the real artifact was supplied. Reproduce with:

```sh
PYTHONDONTWRITEBYTECODE=1 python test_compare_inputs.py
sha256sum -c SHA256SUMS
```

Compact reported hashes establish input identity under SHA256 collision resistance. They do not attest the remote machine or live memfd contents. The independent local full-kernel/native executions remain separate evidence. A failed or incomplete artifact produces a nonzero exit and explicit failure categories rather than being promoted by expected filenames or sample counts.
