# Incremental external checking qualification

Qualification passed: **True**

| Edit | Full obligations | Rechecked | Reused | Fresh verify s | Incremental verify s | Fresh build+export+verify s | Incremental build+export+verify s |
|---|---:|---:|---:|---:|---:|---:|---:|
| no-change | 3436 | 0 | 3436 | 4.513 | 0.183 | 6.254 | 1.924 |
| early-definition | 3436 | 413 | 3023 | 4.457 | 4.228 | 6.216 | 5.987 |
| unrelated-definition | 3436 | 1 | 3435 | 4.398 | 4.499 | 6.377 | 6.477 |
| theorem-leaf | 3436 | 1 | 3435 | 4.273 | 4.009 | 6.258 | 5.994 |
| type-change | 3436 | 2 | 3434 | 4.460 | 4.095 | 6.497 | 6.132 |
| invalid-proof | 3436 | None | 3435 | 4.218 | 3.990 | boundary mutation | boundary mutation |
| axiom-type | 3436 | None | 0 | 4.115 | 4.250 | boundary mutation | boundary mutation |
| toolchain-metadata | 3436 | 3436 | 0 | 4.313 | 4.474 | boundary mutation | boundary mutation |
| malformed-unused-dag | ? | ? | ? | 4.048 | 4.043 | boundary mutation | boundary mutation |
| malformed-unused-typed-node | 3436 | None | 3436 | 3.912 | 4.057 | boundary mutation | boundary mutation |

Authenticated selected-obligation work reduction and exact-export oracle agreement. Timing medians are observations; edit speedup is not assumed. The bounded Lean theorem does not verify the NDJSON dependency extractor or production kernel locality.

Optional kernel statuses: lean4lean=ACCEPT, con-leche=ACCEPT, con-ron=ACCEPT, nanoda_bin=ACCEPT

Failed gates: 
