# MathGraph Serial Warrant V1 — research candidate (not submitted)

## Purpose and source authority

This candidate tests a counterintuitive Arena optimization: **reduce redundant
worker-local computation**, even if elapsed wall-clock time increases.
The leaderboard ranks Mathlib via aggregate retired instructions, not wall time.
Published MathGraph Flash uses two workers; the current Soko source uses four.

The checker is a **transparent composition** of independent existing kernels:
- Primary: Jeremy Chen's sokonanoda at
  `7645b1e1fcacfe410c99141f1234381d995b325d`, with one worker.
- Fallback: Metalogic Labs' existing Flash derivative at
  `78c7502bac8a5ba000057b3f083bc0595ac65750`.
- User-visible source: `experiments/arena_serial_hybrid_v1.sh`.
- Staged *non-submitted* Arena checker declaration:
  `experiments/arena_serial_candidate.yaml`.

This is **not** the standalone Nucleus kernel and does not establish
new kernel rules or independent semantic completeness.

## The partial-verdict composition

For each full export `x`, run the primary from the beginning:

- Primary ACCEPT => composite ACCEPT.
- Primary REJECT => composite REJECT.
- Primary DECLINE or INTERNAL => independently replay `x` with Flash; use
  its verdict, including any refusal. Unexpected exit => composite DECLINE.

Nothing is decided from proof name, path, test index, or known leaderboard outcome.
When both constituent checkers are sound for their accepted/rejected decisions,
this composition is sound. That conditional theorem does **not** itself prove
either constituent checker universally sound.

## Actual fixed-corpus evidence

- [Independent CI 38092404453](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38092404453):
  **125/125 valid ACCEPT, 71/71 invalid REJECT, zero wrong**.
- Only two fallback cases:
  `bad/tutorial/140_falseFromUnsafe.ndjson` and
  `bad/tutorial/141_falseFromPartial.ndjson`.
- No per-test exceptions were added. Direct one-/four-worker Soko verdict
  parity was checked for every portable case.
- Limit: portable suite excludes nine large valid exports, including Mathlib.
  Full Mathlib/PMU instruction and full published-suite qualification are
  separate required authorities.

## Decisive instruction experiment

- [Serial-source/leader PGO Mathlib run](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38092667483)
  compares Soko 1/2/4, Flash 1/2, and optimized Flash 1/2 with exactly
  pinned source and the current Mathlib exporter.
- [Callgrind same-source worker census](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38092741906)
  measures a deterministic guest-instruction proxy. It cannot establish
  official hardware retired instructions.
- Historical [V53](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/33924225976)
  showed aggregate Mathlib CPU time 150.735s (1 worker), 156.805s
  (2 workers), and 253.835s (4 workers), even though wall time was
  fastest at four workers. This was an **older MathGraph source**, not the
  current pinned leader, and is a hypothesis generator rather than a
  current leaderboard performance claim.

## Promotion / rollback policy

**Do not submit or promote** unless the exact submitted build:
1. Replays all published correct-outcome cases without wrong acceptance or
   wrong rejection, including all large exports.
2. Replays the malformed recursor/invalid-axiom negatives. A missing test
   fixture is not a passing regression test.
3. Accepts complete Mathlib, and independent Arena instructions beat the
   current leader under the identical official benchmark.
4. Fits memory and timeout bounds. The serial candidate is expected to
   trade more wall time for fewer total instructions.
5. Retains the upstream attribution and source/commit pinning.

If full Mathlib fails, a bad export is accepted, or total instruction count
doesn't win, leave published Flash unchanged and keep this research branch
unpromoted.
