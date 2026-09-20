# Recovered instruction evidence and bounded cost probe

Objective: reduce Mathlib retired instructions enough to exceed sokonanoda with margin. No official Arena PR or champion mutation is authorized by this experiment.

## Recovered, not rerun

Frozen source: `a342c74f6eb913c25c6dae4138158023d1b9aa6a`.
Arena corpus: `510fbfead6f02bed1a0179d01729a6ddf5bfd06d`.

The raw Callgrind file from run **35491965021**, artifact **10599399542**, was reparsed. All exclusive/self costs reconcile exactly to **779,262,547,912 Ir**. Recursive inclusive call-edge costs are deliberately excluded from this sum.

| Profile family | Exclusive instructions | Share of profile |
| --- | ---: | ---: |
| eval, including recursive clone | 308,720,512,895 | 39.62% |
| prune_env_cold | 83,798,834,321 | 10.75% |
| eval + cold prune | 392,519,347,216 | 50.37% |
| leq_core, including recursive clone | 8,378,178,776 | 1.08% |

These are instruction attributions in an instrumented profile, NOT promised removable costs or a fresh leaderboard measurement. Inlined helpers can be charged to their callers; leq_core self cost is not the complete cost of universe processing.

The earlier Sort identity tournament, run **33144336773**, artifact **9675346239**, used an older lineage and a Std prefix. Best `sort_raw` reduced Ir from **10,003,216,693** to **9,951,199,393** (-0.5200%); native mean changed from 1.640 to 1.654 seconds (+0.8537%). This is not evidence of a large current Mathlib gain.

## Probe question

Where does application-conversion cost occur: forcing values before comparison, or comparing their forced forms? Which residual shapes consume the sampled work? Frequency alone must not choose the optimization.

The original app argument inference remains full Check. Only the conversion call is wrapped. Unsampled conversions use the original conv_types_at unchanged. Sampled roots preserve the original unbudgeted -> force left -> force right -> pointer equality -> unify_general order. Classification is read-only and outside both timed intervals.

Only outermost app-conversion roots are sampled; nested calls remain included in their parent's timed work and are not sampled again. Two deterministic pseudo-random 1/1024 schedules (17, 99173) expose sampling instability. Rows distinguish raw identity/thunks and forced shape, including equal versus distinct Sort level pointers. No new cache, equivalence rule, or accepted-proof shortcut is introduced.

## Budget and interpretation

Thirty-minute job cap. Source compilation and helper tests precede corpus construction. At most one uninstrumented baseline plus two instrumented Mathlib passes, each capped at 250 seconds. No full 409-suite, PGO tournament, or full Callgrind. Cache only the pinned Mathlib export and record its SHA-256.

Timers give sampled native elapsed-time attribution, NOT retired instructions. Timer floor, maxima, seed and raw records are retained. Context switches and sampling variance can distort estimates. No champion promotion or >10% gain claim follows automatically. A new optimization requires a mechanism supported by the cost data; a candidate still requires correctness and matched retired-instruction measurements.
