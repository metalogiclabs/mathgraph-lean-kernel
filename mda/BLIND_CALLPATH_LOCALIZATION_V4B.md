# MDA Blind Call-Path Localization V4b — Lean Kernel Arena

**Status:** frozen protocol, pre-result  
**Parent:** V4a `VERIFIED_BLIND_COMPUTATIONAL_RESIDUAL_LOCALIZATION`  
**Parent run:** `34813702094`

## Question

V4a localized the strongest workload residual to `TypeChecker::eval_no_cache`, `eval`, and `infer_value`.

Without importing the historical optimization story, can the forcing workload further identify **which caller paths are producing the excess uncached evaluation**?

## Frozen presents and encounter

- SEED: mask `2`
- FRONTIER: mask `62`
- Encounter: pinned Arena `con-leche`

## Build

Both presents are built in fixed release mode with:

`RUSTFLAGS="-C force-frame-pointers=yes"`

The frame-pointer change is applied identically to both presents only to make sampled call stacks observable.

## Profiling

Use Linux `perf record`:

- event: task-clock
- sample frequency: 99 Hz
- call graph: frame pointer
- SEED profile window: 20 s
- FRONTIER safety limit: 60 s

## Blind target

The target function is frozen from V4a's top residual:

`<sokonanoda::tc::TypeChecker>::eval_no_cache`

No historical capability label or known repair is supplied.

## Residual extraction

For every sample stack containing the target:

1. identify the immediate caller symbol;
2. count caller frequency;
3. normalize by the number of target-containing samples;
4. compare SEED vs FRONTIER caller shares.

Also rank 3-frame suffix paths beginning at the target.

## Success criterion

V4b passes if:

1. both profiles are produced;
2. at least 50 target-containing samples are observed in SEED;
3. at least one caller or 3-frame path has:
   - SEED share >= 5%, and
   - SEED share at least 1.5x FRONTIER share, or is absent in FRONTIER;
4. a machine-readable caller/path residual table is emitted.

A pass means the workload residual has been narrowed from a hot function to a repeatable calling context. It does not yet prove a repair.
