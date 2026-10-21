# Authenticated producer-delta qualification

Correctness: PASS. Primary changed-input economics: SPEEDUP.

Fresh full native/Python identity and real independent kernels check the exact live sealed composite. Actual selected-kernel counts and independent full-index replay establish the work partition.

| Source edit | Apply median (s) | Direct Rust median (s) | Ratio | Paired wins |
| --- | ---: | ---: | ---: | ---: |
| early-definition | 0.229157 | 0.295608 | 0.7752 | 5/5 |
| unrelated-definition | 0.223641 | 0.302101 | 0.7403 | 5/5 |
| theorem-leaf | 0.249388 | 0.332651 | 0.7497 | 4/5 |
| baseline | 0.188310 | 0.354864 | 0.5307 | 5/5 |

Apply timing includes the producer, authenticated delta identity, actual selected checking and receipt persistence. Baseline seeding and process setup are measured separately and excluded. Each pair uses a new session; the raw full checker receives the same live sealed composite before it is closed, in fixed apply-then-direct order. OS file cache is warm; hosts and workload profiles are not pooled. This comparison does not establish cold-command or total-lifetime superiority.

The primary gate requires lower median, strict paired majority and paired-bootstrap 95% upper ratio below one on the early edit. NO_SPEEDUP is retained as an economic negative and is separate from correctness. Missing required controls are UNKNOWN and block a full qualification claim.

Nonpassing required gates:
