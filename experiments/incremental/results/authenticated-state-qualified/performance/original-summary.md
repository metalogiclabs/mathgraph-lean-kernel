# Authenticated export-state measurements

The primary interval includes constructor/start, every actual source-owned update and supported close. Direct fresh Rust checks genesis and all identical actual revision exports; its input preparation is outside timing. Independent materialization, full-index, kernel and receipt oracles run outside these intervals.

| Profile | Updates | State lifecycle, s | Full-export lifecycle, s | Direct Rust lifecycle, s | State / direct speedup | State / full-export speedup |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| original | 40 | 6.645194 | 7.893787 | 11.911577 | 1.7925× | 1.1879× |
| expanded | 40 | 26.484562 | 32.149496 | 55.110394 | 2.0808× | 1.2139× |

| Profile / warm edit | State per update, s | Direct Rust per update, s | Speedup |
| --- | ---: | ---: | ---: |
| original / early-definition | 0.084613 | 0.291482 | 3.4449× |
| original / unrelated-definition | 0.049185 | 0.291589 | 5.9284× |
| expanded / early-definition | 0.322108 | 1.353400 | 4.2017× |
| expanded / unrelated-definition | 0.295280 | 1.347006 | 4.5618× |

Correctness qualification: CORRECTNESS_QUALIFIED_BOUNDED. Economic status: QUALIFIED_SPEEDUP.

These are same-host warm-cache observations. Cold initialization and expected-head replay are recorded separately. Post-phase RSS/VmHWM are observations, not aggregate peaks. The state receipt is an authenticated construction identity, not a full-export SHA. Full typed-index/applicability loops and cold admission remain O(N); no asymptotic claim is made.
