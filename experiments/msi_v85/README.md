# V85 bounded kernel optimizer

This is an experimental, deterministic, no-API optimization controller. It does not change the production kernel. Frozen kernel: `08ddb26718c86213262943ca19ae8cf1b03fa922`; frozen arena: `91f376e4baacf2df0c478e7173bccb2a6adac5c5`.

The first candidate set tests compiler/code-layout hypotheses at measured v83 hotspots: always-inline and never-inline spine construction, and never-inline evaluation. These are not new reduction rules, and the controller does not claim to invent arbitrary optimizations. A later candidate set requires an explicit, reviewed source recipe.

One job builds the corpora once and reuses a Cargo target directory. Each candidate must compile, differ from the champion binary, replay Std/Cedar exactly, survive two balanced screening passes, then replay Mathlib and survive a short Mathlib screen. Only promising candidates enter five complete three-corpus passes and three separate confirmation passes. The unchanged champion is measured twice as an A/A noise control. Promotion requires at least 1% geomean improvement, no corpus more than 1% slower, and A/A drift within 1%. All thresholds are exploratory, not confidence intervals.

The controller has a global limit of two cycles, seven builds, two full evaluations, and 150 minutes. It records every decision in a flushed ledger. Failed candidates are rejected; successful candidates become provisional benchmark champions only after confirmation. Later cycles compose compatible unused recipes with that champion. A negative result or exhausted budget stops rather than inventing another candidate. A kernel failure, timeout, or infrastructure failure is never a gain.

The result includes the exact binary hashes, corpus hashes, timings, rejected candidates, and a final patch/binary when a candidate is promoted. Exact replay is on the frozen corpora only; it is not a universal correctness proof, an unseen benchmark result, or proof that a specific low-level mechanism caused the gain. Production retention requires separate review and validation.

Run unit tests with `python3 -m unittest discover -s experiments/msi_v85 -p 'test_*.py'`. Run the actual experiment using `bash experiments/msi_v85/run.sh` in a Linux environment with Git, Python, Cargo, and Nix. The GitHub workflow is the intended execution environment. No credentials or external model services are required.