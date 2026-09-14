# MDA Blind Residual Localization V4a — Lean Kernel Arena

**Status:** frozen protocol, pre-result  
**Repository:** `metalogiclabs/mathgraph-lean-kernel`  
**Branch:** `mda/blind-residual-localization-v4a`  
**Parent frontier result:** `VERIFIED_WORKLOAD_ENVELOPE_BIDIRECTIONAL_FRONTIER`  
**Parent run:** `34812829051`

## Question

Can the workload residual that forces growth beyond the minimum semantic kernel be localized **without supplying the historical optimization story or capability names**?

V4a does not attempt invention yet. It tests whether the consequence itself exposes where the seed is spending work.

## Frozen presents

- **SEED**: mask `2`, the minimum semantic kernel.
- **FRONTIER**: mask `62`, the unique V3b minimum workload-sufficient frontier.

These labels are used in the experiment. Historical capability descriptions are not used by the profiler or residual ranking.

## Frozen encounter

- `con-leche` from pinned Lean Kernel Arena `ac1c13762de41b594fa24b90ede8cfd97ac6a765`.

The exact workload artifact is reused from V3 run `34807040127`.

## Ground

Before profiling, both presents must freshly pass:

- `cargo test --release --locked`;
- `init-prelude` accept;
- `extra-rec` reject;
- `rec-missing-ih` reject;
- `proj-of-stuck-prop` reject;
- `proj-of-subst-prop` reject.

## Profiling protocol

Build both presents in the same fixed release mode.

Use Linux `perf record` with task-clock sampling at 199 Hz.

- SEED profile window: 25 seconds, then controlled termination.
- FRONTIER: profile to completion, with a 60-second safety limit.

Generate exclusive (`--no-children`) symbol profiles.

## Blind residual score

Let `p_seed(s)` and `p_frontier(s)` be exclusive task-clock percentages for symbol `s`.

For every symbol observed in either profile:

[
R(s) = p_{seed}(s) - p_{frontier}(s)
]

Rank descending by `R(s)`.

Also report:

- symbols unique to SEED above 0.5%;
- symbols whose SEED share is at least 2x FRONTIER share;
- the cumulative residual mass in the top 5 and top 10 symbols.

No symbol category or subsystem is privileged in advance.

## Success criterion

V4a passes if:

1. both presents pass semantic replay;
2. both perf profiles are successfully produced;
3. at least one residual symbol has:
   - `p_seed >= 1.0%`, and
   - `R >= 0.5 percentage points`;
4. a machine-readable ranked residual table is emitted.

A pass means only that the forcing workload yields a localized computational residual. It does not establish that a successful repair can be invented from that residual.

## Claim boundary

This is a localization experiment over one protected workload and two frozen presents. It does not establish causal necessity of any named function, and it does not use official Arena retired-instruction measurement.
