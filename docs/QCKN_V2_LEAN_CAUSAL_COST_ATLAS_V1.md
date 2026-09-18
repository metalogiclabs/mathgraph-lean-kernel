# QCKN V2 Lean Causal-Cost Atlas V1

## Status

Preregistered successor to the preserved RED result from GitHub Actions run
`35343216790` at commit
`731da4ad2abf1461223a47620fbf584908cdec0f`.

This experiment may confirm or reject one bounded obstruction. It cannot
promote a Lean optimisation selector.

## Prior RED

The depth-64 selector retained `0.967984` of observed beta-fusion activations,
but achieved only `1.003369075x` on the frozen source workload against a
preregistered `2.0x` floor. The first exact obstruction was:

`SOURCE_COST_GATE_FAILED: perf/beta-ladder speedup 1.003369 is below 2.000000`

The typed bounded obstruction is:

`ACTIVATION_COUNT_NOT_COST_CONSEQUENTIAL`

It means only that activation frequency is not a sufficient selection
criterion for this R1 depth-threshold family under the named Arena commit,
workload, build, and Callgrind authority boundary.

## Frozen experiment

- Arena commit: `510fbfead6f02bed1a0179d01729a6ddf5bfd06d`
- Workload: `perf/beta-ladder`
- Arms: R1 off, then minimum depth `0`, `8`, `32`, and `64`
- Build: the same PGO x86-64/no-AVX procedure for every arm
- Cost: Callgrind instructions only
- Correctness: status zero and identical stdout digest for every arm
- Activation retentions: the frozen activation-atlas values

For threshold `d`, causal savings retention is:

\[
\frac{I_{off}-I_d}{I_{off}-I_0}.
\]

No metric or denominator may change after the run starts.

## Gates

The result is `OBSTRUCTION_CONFIRMED` exactly when depth 64 has activation
retention at least `0.90` and causal savings retention below `0.90`.

The run is RED immediately if any arm fails acceptance, any stdout digest
differs, an instruction count is unavailable, unrestricted R1 does not improve
the source cost, or the prior obstruction is not reproduced. The latter verdict
is named `PRIOR_RED_NOT_REPRODUCED`; it must not be rescued by another metric.

## Compiled RED capital

The exact prior RED is compiled as a one-input `FiniteCapability`:

`ACTIVATION_COUNT_SELECTOR -> RUN_CAUSAL_COST_ATLAS`

Its authority and verifier are inherited from the exact prior run. Its scope is
the named finite boundary above. It saves one repeated search decision; removing
it restores that cost. The full counterexample remains provenance, while the
restarted CompiledPresent contains only the independently checked bounded
capability and no historical episodes.

This is a search-routing result, not an optimisation promotion and not a claim
that activation counts are generally useless.
