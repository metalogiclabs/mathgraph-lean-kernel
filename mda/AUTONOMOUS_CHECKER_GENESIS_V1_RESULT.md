# Autonomous Checker Mechanism Genesis V1 — Result

**Frozen protocol:** `1fc7f1aea30a8f5de7541bfa4d718d9002bed4d4`  
**Starting checker:** `c6d445a954def8922490d0cd874ea134b45463dd`  
**Successful training run:** 34827699468  
**Job:** 103923538147  
**Artifact:** 10342156950  
**Artifact digest:** `sha256:cfd1525587c40d5e0958e1a0eab1334e60bda13b82d8b66cbfcae72a5c5006aa`

## Verdict

```text
UNKNOWN_NO_TRAINING_WIN
```

The experiment remained inside the frozen training-only phase. No candidate was selected for the semantic gate, so held-out workloads were never opened.

## What completed

- all four frozen training workloads built;
- 38 release tests passed before census;
- real open-cache hit/miss census completed on all four workloads;
- all 30 frozen threshold laws were generated;
- they collapsed to 11 distinct policy behaviors;
- every distinct behavior plus the all-bypass control compiled and ran;
- the frozen >=1% aggregate training promotion threshold was not met.

## Key training observations

Baseline wall times (two reps):

- con-leche: 16.83, 16.94 s
- app-lam: 0.03, 0.03 s
- beta-ladder: 0.53, 0.51 s
- let-ladder: 0.02, 0.02 s

A representative best-looking generated policy, `h8_r0p01`, ran approximately:

- con-leche: 16.68, 16.92 s
- app-lam: 0.04, 0.03 s
- beta-ladder: 0.52, 0.50 s
- let-ladder: 0.02, 0.03 s

This was below the frozen 1% aggregate promotion requirement.

The all-bypass negative control strongly worsened con-leche to 25.18 s while slightly improving beta-ladder to 0.46 s, proving that the cache is valuable in some contexts and costly in others.

## Residual

The frozen observation language

```text
root kind × FV-mask bucket × evaluation-depth bucket
```

is too coarse to earn a mechanism change.

The lawful next move is observation-language development: refine the local structural context without lowering the frozen economic threshold or promoting a sub-threshold policy.

No semantic or held-out promotion claim is made for V1.
