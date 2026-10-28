# Graph-native nucleus V3 — in-lifetime cache budget intervention (frozen)

## Residual and prior evidence

- The original source uses `SESSION_BUDGET = 16 * 1024 * 1024`, a resettable per-worker bump arena, and `SessionCache::enter`/`clear_session`; the native checker does not permit values allocated in a reset arena to outlive that reset.
- Full-Mathlib V1 source-identity census observed 146,638 cache resets, 72,249 recurrent 1/256-sampled closed-evaluation misses, and 787,731 eligible sampled cache hits. These are NOT proven recomputation cost or saved instructions.
- ROS recorded negative Callgrind results for three more sophisticated prune-cache reuse interventions (approximately +2–3% guest instructions), so this test makes no persistent semantic equivalence or new cache representation assumption.

## Frozen intervention and controls

1. Baseline: exact same source checkout, ordinary Rust release build, **16 MiB** `SESSION_BUDGET` per worker (original, not probe feature).
2. Candidate: identical source and release flags, Cargo feature `session-budget-64` changes only the per-worker session allocation threshold to **64 MiB**. The same cache is valid within each original session; no value, proof, hash, or environmental equivalence is transferred after a reset.
3. Same original Lean Arena `b83254de5146ef34147ab82a48edbe1856b0edcc`; 6,184,415,052-byte Mathlib SHA256 `22c5de83469408950005589a3bc5ef5157c65549b5a802f85d567c29151306a6`; native four-worker stdin JSON config.
4. Both variants must exit successfully and emit *exactly* `Checked 718577 declarations with no errors` on every trial. Do not merge candidate into default or official Arena before an independent speed/semantic qualification.
5. Test both default and feature contract tests before measurement. Build independent binaries from the same revision with `RUSTFLAGS='-C target-cpu=x86-64'`; record SHA and source identity.
6. Three same-host CPU/wall/RSS paired repetitions, order **A/B, B/A, A/B** to partially counter run order. Use six full native checks; `/usr/bin/time` counts are operational data, not PMU-retired instructions or causal guest Ir.

## Predeclared screen and stopping rule

- `INVESTIGATE_GUEST_IR`: all three paired candidate/user-CPU ratios below 1.0, geometric mean candidate/base user-CPU ratio at most **0.98**, candidate peak RSS at most **1.10×** baseline in every pair, and all six acceptance/verdict checks identical. Then commission matched 5-case Callgrind guest-Ir (>=1% geometric gain, <=2.5% worst-case regression) plus held-out invalid controls before full-performance promotion.
- `REJECT_64_MIB_BUDGET_SCREEN`: no such measured screen. Do not tune more budget sizes post-exposure and retrospectively claim a prospective win; any follow-up is a newly frozen hypothesis.
- `INVALID`: frozen source hash, binary build, complete acceptance, pair accounting, or reproducibility conditions fail; no performance interpretation.
- Regardless of result, three CPU pairs are not independent hardware-retired-instruction evidence or universal improvement, and this branch makes no new persistent-reuse claim.
