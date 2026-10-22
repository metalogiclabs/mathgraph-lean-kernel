# Authenticated-state cost arithmetic

CONTEXTUAL_EXACT_SOURCE_5X40_ARITHMETIC. Contextual arithmetic only; no new correctness authority.

Source `cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5`; exact summary SHA256 `49995dee47cc470604db8f35bfbeea704c5b55614b97274a7b1856514499f25d`.

| Profile | State lifecycle, s | Full export, s | Direct Rust, s | State/direct reduction | State/full reduction |
| --- | ---: | ---: | ---: | ---: | ---: |
| original | 6.645194 | 7.893787 | 11.911577 | 44.212% (SPEEDUP) | 15.817% (SPEEDUP) |
| expanded | 26.484562 | 32.149496 | 55.110394 | 51.943% (SPEEDUP) | 17.621% (SPEEDUP) |

Full producer/authentication/identity/selected checking/persistence and supported close are inside each candidate timer. Direct input preparation is outside timing. Raw pairs, ten-update per-edit means (four-update smoke: one), CPU, cold components, nested phases, logical cache sizes and per-process memory remain in JSON/CSV.

Promotion is included in persistence. State materialization_and_hash is a delta-only recipe phase; no full-export SHA is claimed. Full-export byte counts are derived; state zero counts are recorded. Procfs RSS/HWM samples establish no aggregate peak. Cold admission/history replay and remaining index/applicability loops prevent any asymptotic total-work claim.
