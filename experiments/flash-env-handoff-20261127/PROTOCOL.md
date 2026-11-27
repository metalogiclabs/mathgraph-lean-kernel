# Environment handoff and frame-copy experiment

Objective: lower Flash's current-round Mathlib instruction cost while keeping
all prescribed checker outcomes. Base source is bc704eebed4e009bc66af1a849f18315c11f1926,
src tree 06c257f0f2ff1f64711cfa54620b650e6dd59b7e. Prior skip/reuse,
cache-capacity and context-span negatives remain separate; none is combined.

- [x] Freeze the released source and preserve prior failed cost gates.
- [x] Count repeated exact projections, frame reuse and contiguous selections.
- [x] Test reuse of the projected environment inside type inference.
- [x] Test contiguous frame-slot copying as an independent change.
- [x] Test their interaction with a fourth arm.
- [x] Qualify the selected projection arm: 230/230 portable, 39 library tests, 16 source controls.
- [ ] Other-arm broader qualification: frame-only 229 plus one SIGKILL; combined release library build SIGKILL. Both remain incomplete.
- [x] Require a repeated material prefix instruction reduction.
- [ ] Qualify complete Mathlib for a surviving arm.
- [ ] Qualify the nine other large cases before a new release submission.
- [ ] Obtain official native retired-instruction scoring before a rank claim.

The inference arm runs inference using the exact environment projection it
already computes for its cache key. Expression dependencies determine that
projection; depth, context values, checking mode, universe scope and all
validation checks remain in place. The copy arm recognizes a fully selected
prefix of a framed environment and reads its consecutive value slots directly;
sparse selections retain the existing rank calculation.

An observation-only build counts work without supplying speed evidence. Its
exact-key sets are cleared whenever value storage resets. Production arms
contain no census instrumentation. Each executable is frozen before testing.

The screen uses the exact 134,232,002-byte, 25,131-declaration Mathlib prefix
SHA-256 c3d1e08032bbfe2dbfc4c8a84fd711ba83296a47d7468d9ce15988efa4acfa3a.
Same generic x86-64 compiler flags, two workers, two alternating rounds,
calibrated DynamoRIO basic-block counter, raw exits and complete declaration
counts. Before candidate measurement, two identical baseline runs establish
the threshold max(1%, twice their fractional instruction range). A survivor
must beat that threshold in both pairs and aggregate. CPU and RSS are measured
separately on the same executables, not substituted for instructions.

Full-Mathlib promotion additionally requires all 739,167 declarations accepted
on the exact input, repeated instruction savings, CPU regression at most 3%,
and peak RSS growth at most 10% or 256 MiB, whichever allowance is larger.
Software counts are diagnostic; they never establish an official Arena rank.
Failed apparatus, signals and unexecuted gates remain UNKNOWN. No production
release or existing research branch is changed by the experiment.
