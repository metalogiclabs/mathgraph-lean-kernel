# Preserved harness development checkpoint

The first local draft run used `/workspace/kernel-audit/qualification` and the
genuine exports retained under `/workspace/kernel-audit/workloads`. It was run
while the adapter source was still changing. Authentication correctly refused
reuse when that source identity drifted: every qualifying edit performed all
3,436 obligations instead. These failed savings gates are not evidence against
the final frozen predicate and are not silently counted as a successful run.

The draft also exposed a harness error: copying immutable cache records preserved
their read-only mode, so the deliberate corruption control raised PermissionError
before changing the copied file. The final harness explicitly makes only each
adversarial copy writable before corrupting it. Original evidence remains intact.

The draft independent baseline runs all accepted: official C++, paranoid C++,
lean4lean, nanoda, con-leche verified, and con-ron verified. The fully sandboxed
`lake check --from-export ... --paranoid` also accepted and reported only
`propext`, `Quot.sound`, and `Classical.choice`.

The final run uses a fresh output directory and a frozen adapter, adds actual
executable-byte drift and a malformed unused DAG row, and preserves all command
reports and output files. The final artifact, rather than this checkpoint, is the
authority for qualification and resource claims.
