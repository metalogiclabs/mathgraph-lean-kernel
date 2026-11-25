# Flash early evaluation-cache experiment

Both implementations are **REJECTED for performance promotion** on the declared
five-case instruction comparison. Neither is a release candidate or an Arena
submission. The source is retained on an isolated research branch for replay.

The baseline is the corrected current-round release
`819d59c34db3fd8f7b790a83f5728f255f75f33e`. Flash normally projects an
expression's environment before looking in its evaluation cache. The hypothesis
was that an exact original-environment lookup could avoid this repeated work.

| Implementation | Geometric mean candidate/baseline guest instructions | Decision |
| --- | ---: | --- |
| Extra aliases in the existing growing map | 1.1235131786 | Reject: 12.35% more |
| Separate bounded 1,024-entry exact-key table | 1.0169888908 | Reject: 1.70% more |

All five measured cases regressed in both versions. Cases: Init prelude,
grind-ring-5, magma-list-deep-n21, magma-list-pair-n7, fueled-chain.

## Authorship and attribution

The new control flow, bounded table, tests and experiment harness were written
for Flash from its existing implementation. No competitor implementation was
copied. The conceptual comparison was nano-lean's practice of probing an exact
environment before constructing a projected one:
[pinned source](https://github.com/sdiehl/nano-lean/blob/5cd4a25de7cdd8a5fadde3fec53e41a6a8693138/src/value_checker/eval.rs).
This is not a claim that the general caching technique is new. Flash retains
its existing attribution and its sokonanoda-derived implementation.

Two missing recursor regression fixture files were restored separately in commit
`ca69e6ab8a3c7b795716128372fdaf67c697b68e`. Their inputs derive from a Lean Kernel Arena tutorial, with the exact
source hash, license and mutations recorded in `fixture-provenance.json`.

## Verification boundary

- rustc 1.99.1, locked dependencies, identical generic x86-64 flags in both arms.
- Software Callgrind guest instructions, one worker, one observation per arm and
  case. These are not hardware retired instructions or an official Arena score.
- Each measured input matched the size and SHA-256 in official run
  `45581042122`, revision `cb0665b7b0f34d53fa8d62584535c27c86dfa982`.
- The replay-cost test failed on the baseline (projection count 2 to 3) and passed
  after the change. Captured values, universe substitutions and both invalidation
  paths are controlled. The bounded version also tests collision replacement.
- Full bounded-candidate Rust suite: 51 library tests and one integration test
  pass; four pre-existing documentation examples are ignored. The integration
  test has no installed Arena tree here; it is not an additional corpus result.
- Both original release tests failed before restoring the missing recursor
  fixtures. The restored baseline library suite passes all 46 tests.
- Alias-version portable comparison: 228/230 strict correct verdicts in each
  arm. Both processes were killed with SIGKILL on magma-list-deep-n36 and
  magma-list-pair-n21; the underlying cause is not established. These remain
  unavailable, not semantic rejections or completed qualification.
- No full Mathlib measurement or ten-large-case candidate qualification was
  attempted after the performance gate failed. Published-release qualification
  and the pending leaderboard deployment are separate evidence.

`alias-rejected.json`, `bounded-rejected.json` and their row files preserve the
measurements. `census.json` records a separate instrumented native work count;
it does not supply timing evidence. No new optimization is warranted by it.

## Replay

Build the baseline and each experiment revision with identical flags:

```sh
RUSTFLAGS='-C target-cpu=x86-64 -C target-feature=-avx,-avx2,-avx512f,-fma' \
  cargo build --release --locked
```

With official results.json and a portable fixture tree arranged as
`FIXTURES/tutorial/...ndjson`, run:

```sh
python experiments/flash-early-eval-cache-20261126/compare.py samples \
  --results RESULTS.json --fixtures FIXTURES --baseline BASELINE_BINARY \
  --candidate CANDIDATE_BINARY --out OUTPUT --valgrind valgrind
```

Use `portable` in place of `samples` for the complete 230-input portable attempt.
Every input is hash-checked; raw statuses are preserved. `--rounds 2` alternates
the comparison order. The admission criterion is at least 1% fewer guest
instructions geometrically over the five cases, before any expensive full
Mathlib candidate qualification.

For the diagnostic, create a disposable checkout of alias commit `492480f59fbdfebaa80180ead495ff4fe143d4c6`, run
`instrument_census.py CHECKOUT`, rebuild, and check the same five inputs. Counter
order: exact original-environment hits, projected-environment hits, computed
misses, extra alias insertions, unprojected insertions. Counter overhead makes
that binary unsuitable for performance measurement or promotion.

## Residual

The new lookup can skip environment projection, but its additional probe,
insertion and memory costs exceed that saving on this comparison. Future work
needs a cheaper representation or a measured reduction of actual evaluator
misses; these results do not support adding another similar lookup layer.
