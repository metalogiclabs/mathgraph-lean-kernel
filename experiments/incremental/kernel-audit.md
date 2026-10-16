# MathGraph kernel reconstruction checkpoint — 2026-10-16

Read-only inspection of full refs in `/workspace/mathgraph-lean-kernel`; only audit files outside the checkout were created. No official Arena submissions, workflow dispatches, repository mutations, or communications were performed. No AGENTS.md was found under /workspace.

## Recommended base

Use `origin/flash` / `origin/flash-2-inferpi-thread2-candidate-v1` at **78c7502bac8a5ba000057b3f083bc0595ac65750**. The current research branch `origin/arena-soko-keyed-closure-reuse-v1` at **9588f87993781c3250b8310a090e1b39c62c044d** has the **identical entire src tree**, tree SHA `dc8e57cc04aa039a87d5e730866beb652fb89e68`; Cargo.toml and Cargo.lock are also identical. Thus using the keyed branch as a research-script base gives the same core as qualified Flash. The branch's experiment modifies an external cloned upstream during CI; it does not integrate that Soko patch into the MathGraph src directory.

Master `59570dbc8c57b76f1a6872b1499a2977a673cdad` has older src tree `f2d44f6cf4566d0b17f7e2c4a65bc4f2feab6d7b`. Diffing master to Flash affects 20 source files, with 1444 additions and 2052 removals. In particular, master's tc.rs only checks that each recursor-associated inductive name exists. Flash checks recursor index membership in the associated mutual block and verifies each name is an inductive in the same block. The Sept 5 `7b51784fe4ec9b82bf7a20c71ba6bf803a4ed7c0` upstream-fix port contributes extensive inductive checks. Prefer the qualified later core rather than extending master's unsafe caller-trust surface.

Directly queried [run 35596011019](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/35596011019) at exact Flash SHA. Job 106320847257 reports successful build, pinned full corpus build, and **Full 409 exact semantic parity**. Workflow source pins Arena `510fbfead6f02bed1a0179d01729a6ddf5bfd06d`, requires exactly 409 exports, and compares exit status plus stdout against RC1 source `a342c74f6eb913c25c6dae4138158023d1b9aa6a`. This is empirical qualified parity, not a universal soundness proof. Earlier RC1 qualification [35418749010](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/35418749010) independently reports all semantic/PGO/regression steps successful.

Do not mistake newer `origin/flash2-whnf-nostore-final-promotion-v1` at `c6465d083bfb58dbb1732034898ba584edfad0b6` for a later completed qualification. The final workflow was replaced by a PMU-privilege probe. Run 35963148067 succeeds for that probe only; preceding real end-to-end runs failed. No newer broad qualified MathGraph core established in this inspection.

## Existing incremental API: reusable code, incomplete trust boundary

`origin/experiment/incremental-ai-loop` at **88cc2415104a3607c68d51e2890bcdd10cac3395** has the implementation closest to the requested cross-development behavior. Commits:

- `023449c7abf986c13ae6e1438c348bde20df2c2f`: add `ExportFile::declaration_count()`, `check_declars_from(start)`, and `check_last_declar()` in src/tc.rs.
- `9d12ff534932c38635fb1f110a33d202fb3b7468`: add `check_last_declar_direct()` to invoke exact existing `check_declar(d)` and `EnvLimit::ByName` visibility while avoiding scheduler/thread overhead. That commit also accidentally adds a duplicate proposition call; `f83773df059e2117e562d5d39934ce60d2dab95c` removes it. Copy only the narrow API, not unrelated historical hunks.
- `88cc241...`: CLI `--profile-last-repeat N CONFIG` reparses an export from scratch for every repeat, then calls the direct last-declaration path. Full-repeat profiling creates a fresh global arena/parser/check each loop. These are latency probes, not persistent state reuse.

The exact reusable API text has been extracted to `/workspace/kernel-audit/incremental-api-reference.rs`. It consists of approximately 60 lines inserted before `check_all_declars_serial()` in the `impl ExportFile` block. `check_declars_from(start)` validates only `start <= total`, then runs `run_session((start,total), || None)` on a large-stack thread; `check_last_declar_direct()` reads the final declaration and calls `self.check_declar(d)`. There is no prefix-validation object, no identity check against prior verified declarations, no durable receipt, and no automatic fallback upon mismatch. The source itself explicitly says it is sound only if skipped declarations have already been verified and remain immutable.

No dedicated successful CI qualification for this incremental branch was found. Recent branch runs listed are unrelated inherited workflow parse failures. It also predates the later upstream inductive fixes, so port only the minimal API to qualified Flash (same existing run_session/check_declar mechanics) and add actual checked-prefix provenance there.

Smallest gap: after a full cold check succeeds, create a kernel/config-bound receipt for the exact immutable declaration prefix; on a later full parse, compare that prefix exactly (including names, levels, expressions, declarations, inductive/recursor block boundaries and all policy inputs) before calling the suffix API. A changed prefix or unmatched receipt must cold-check. A bare caller-supplied numeric start index must never count as evidence. This closes the actual gap between the historical suffix primitive and verified cross-development reuse. Prefix granularity must respect entire mutual-inductive blocks.

## Cache reuse that is not cross-development reuse

### Keyed closure experiment

`9588f879...` implements `experiments/arena_soko_keyed_closure_reuse_patch_v1.py`, applied by its workflow to **external Soko** `intgrah/sokonanoda@7645b1e1fcacfe410c99141f1234381d995b325d`, with prior sparse+growth patches. It avoids a second `key_env(env,e)` call when eval already passed the keyed environment into open Pi/Lambda `eval_no_cache`. Closed terms still call key_env to preserve level substitution. This is intra-evaluation idempotence reuse with no persistent state.

[Run 38109875237](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38109875237), job 114383034254, is successful on actual build/test, exact196 verdicts, five guest-Ir pairs, and artifact upload. Workflow/duel require 125 accepted, 69 rejected, two declined, equal baseline/candidate outcomes, then measure Callgrind guest Ir and RSS on five selected cases. The performance decision is written into a JSON report; the CI does **not** fail just because the measured candidate is unhelpful. Therefore successful workflow alone establishes that checks completed, not that performance improved or promotion was warranted.

### Checked capability V1/V2

V1 branch **7ecafdc446825346ce7a703ed36df00ff7842e1b** has a tiny patch: declarations with no universe parameters share `CheckScope::NoUparams`, instead of `Under(empty uparams pointer)`. It changes the eligibility of a type-cache entry whose key is `(key_env pointer, ExprPtr)` and stores `CachedType { result, checked_under }`. [Run 35518698266](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/35518698266) is successful through all 409 parity/native PGO/full Mathlib Callgrind steps. No durable checked declaration or cross-run object exists.

V2 branch **1580d52e6ca38a3e06f386711a006e0fcab8cabe** extends the same scope sharing to expressions structurally proven universe-parameter-free, cached by ExprPtr. [Run 35532651042](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/35532651042) was **cancelled during corpus construction**; semantic/native/Callgrind steps were all skipped. Do not claim V2 qualification.

`TcCache::clear_session()` clears the type cache and other arena-pointer keyed caches; `SessionCache::enter()` unconditionally calls it after each session. The lifetime-bound entries cannot safely transfer into a new parse/process by copying pointer keys. Retaining allocation capacity is not retaining checked facts across development runs.

### Cache-reuse V87

`experiment/cache-reuse-evidence-v87` deliberately preserves only a structural free-variable memo over immutable values across declaration-level clear, then clears it at `clear_session`. Focused tests assert no stale entries survive sessions. Its preflight may succeed despite known failed negative tests, while explicitly setting `release_qualified=false` if missing negative fixtures exist. Workflow green does not establish full soundness release authority. This is another within-session optimization.

## Evidence availability and limits

GitHub API run/job/step conclusions and exact checked-out workflow/source were directly inspected. Artifact metadata was directly inspected for keyed closure (artifact 11691572905, digest sha256:73aa23fef45cd692c5b7d1bcef951186137ab2f88dd22facda7295404143fbe5) and Flash full parity (artifact 10638422729, digest sha256:e2a3937548d4eb4afaa3c4cf5311f8a61901de397a5d61f58bc4fce3f77b3949). Download attempts for logs/artifacts were denied with HTTP Forbidden on the Azure blob redirect in this environment. Therefore raw per-case artifact rows and measured keyed-closure speedups were not independently read here; do not cite guessed figures. No green-run result should be stretched beyond its exact assertion logic.
