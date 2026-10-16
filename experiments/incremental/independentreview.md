# Independent final qualification review

Status: **PASS_WITH_STATED_ASSUMPTIONS**

Reviewed 72 actual engine results, their authenticated receipt partitions, all ten pinned exports, both mandatory raw independent-kernel runs per export, and Rust source/build/binary provenance.

- Baseline and each edited development contain 3436 flattened obligations, while the export has 3145 top-level declaration records because inductive blocks expand into types/constructors/recursors.
- Early definition changes Nat literal 17 to 23 at flattened index 9; it rechecks 413 obligations and reuses 3023, including later unrelated definitions and leaf theorem. Rust reports checked 413.
- Invalid proof schedules changed leaf index 3433; genuine kernel rejects, completed recheck count remains unknown and no new evidence is issued.
- Axiom-type change causes a full fallback and rejection; no former accepted warrant can accept the changed environment.
- Changed unused ill-typed DAG nodes reach the actual Rust parser even with zero selected obligations; exact attested unchanged bytes are the only parser-skip case.

The local run began at 367288d; clean rebuild 9ac0403 has identical kernel source and matching recorded harness hashes. The selected and full binary SHA256 values match the qualification and build manifest.

- The dependency extractor and production kernel locality are audited assumptions, not a proved metatheorem.
- HMAC authority is local trusted adapter issuance after successful checking; secrecy and integrity of the separate authority key are required.
- The low-level Rust selected-check binary is not a standalone full-export certificate.
- Benchmark timings are observed medians, not an official Arena performance result.

Errors: []

Fresh reviewer replay: all nine direct Rust/C++/paranoid outcomes agreed on the early edit and both malformed proof/axiom variants. Actual selected counts were 413, 1, and 3436 respectively. Raw commands and outputs are embedded in the JSON review.

Timing limitation: the unrelated-definition median was 4.398 s fresh and 4.499 s incremental despite checking one obligation. The review establishes work reduction and bounded oracle agreement; it does not claim every edit speeds up.

Complete machine-readable review: [independent-review.json.gz](results/independent-review.json.gz).
Decompressed SHA256: `970d31c3405766024def83f49103235a59db8a02d3d174acf123727b8e202b1d`. Decode with `gzip -dc`.
