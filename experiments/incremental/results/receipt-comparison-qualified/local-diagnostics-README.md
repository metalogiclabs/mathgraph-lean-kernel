# Local continuation diagnostics — no performance qualification

Target source: `5dfe38b01ca7b1c67f70be4ffb2479978049239e`; target workflow run: `39581949051`.
This is a self-contained collection of diagnostic records/review helpers, not a five-pair
qualification, complete raw-input replay bundle, or claim about a pending CI result.

The exact downloaded old `6e717043b85acdad63c2399131cb5f9a7432ee37` artifact is unchanged:
`retained-kernel-admission-6e71704.zip`, 2,761,169 bytes, SHA-256
`0532de6895cf6c573fe81213cc6f62749aa8049d2b1640686cc57fcd9c9310cb`.
Its primary early-edit warm gates remain **NO_SPEEDUP in both profiles**. All original
per-case classifications remain verbatim, including the original unrelated-case result.
No local diagnostic changes or promotes the historical classifications.

Contents: normalized old provider metadata/job logs, independent artifact/boundary/equality
reviews, frozen old source snapshots, local red/green logs, operation-profile summaries and
profiler text, small raw kernel verdict/command records, one-pair cross-mode smoke metadata,
and final witness packaging validation/manifests/compact receipts. The local 5dfe kernel
replay is correctness evidence only, not a performance claim.

DIAGNOSTIC-PROVENANCE.json retains actual reported source hashes and dirty status. The
after-profile and one-pair smoke ran with Git HEAD 6e71704 plus dirty changes. They must not
be relabelled clean 5dfe CI measurements. The smoke headers say repetitions=5, but only one
sample is recorded and run_completed=false; the explicit one-pair status governs. Earlier
source/operation profiles preserve their own reported 6e source and remain diagnostic.

Excluded: issuer/authority key files, credentials, sessions/cache trees, raw NDJSON, pstats,
full indexes/results and duplicate baseline gzip/content. The downloaded ZIP is preserved
once, without its extracted duplicate tree. Historical witness manifests/SHA256SUMS can
refer to deliberately omitted data. Packaging validation records describe the original
local check and do not imply every referenced blob is inside this archive.

local-diagnostics-files.txt lists every member. local-diagnostics-manifest.json records
length/hash/original path/category for data members, excluding itself and SHA256SUMS to
avoid self-reference. SHA256SUMS additionally covers the manifest. Gzip/tar timestamps,
owners and modes are normalized; two in-memory archive builds are byte-identical.
No Git, runtime source, or ROS state was modified by packaging.
