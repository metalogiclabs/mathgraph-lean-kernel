# Actual independently recomputed performance

Qualified runtime source `cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5`; [successful CI run39709067518](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/39709067518). This review exactly reproduces all28published economic series with the frozen stdlib helper. It reviews arithmetic and measurement scope; semantic acceptance correctness belongs to the separate CI and independent replay evidence.

| Workload obligations | Direct fresh Rust lifecycle | Prior full-export adapter | Authenticated-state lifecycle | Reduction vs direct | Speedup vs direct | Reduction vs prior |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 3,436 | 11.911577s | 7.893787s | 6.645194s | 44.2123% | 1.792510× | 15.8174% |
| 11,653 | 55.110394s | 32.149496s | 26.484562s | 51.9427% | 2.080850× | 17.6206% |

Five paired uninterrupted lifetimes per workload. Each candidate includes constructor/start, genuine genesis admission,40actual source-owned updates, evidence persistence and supported close. Direct performs41fresh Rust commands on identical actual exports; input preparation is outside its timer. All comparisons above won5/5pairs and their95%paired-bootstrap ratio upper bounds are below1.

| Workload / warm edit | Direct Rust | Prior adapter | State | Speedup vs direct | Reduction vs direct | Reduction vs prior |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 3,436 / early-definition | 0.291482s | 0.117295s | 0.084613s | 3.444874× | 70.9714% | 27.8626% |
| 3,436 / unrelated-definition | 0.291589s | 0.078225s | 0.049185s | 5.928413× | 83.1321% | 37.1237% |
| 11,653 / early-definition | 1.353400s | 0.428339s | 0.322108s | 4.201692× | 76.2001% | 24.8006% |
| 11,653 / unrelated-definition | 1.347006s | 0.404070s | 0.295280s | 4.561787× | 78.0788% | 26.9235% |

Warm times are medians of five per-pair ten-edit means, not medians of fifty individual latencies. All eight primary warm comparisons (both edits, both workloads, both comparators) individually pass, with5/5wins and ratio upper bound below1. Restoration comparisons also pass.

| Workload | State lifecycle CPU | Direct CPU | CPU reduction vs direct | State cold initialization median | State expected-head40-replay |
| --- | ---: | ---: | ---: | ---: | ---: |
| 3,436 | 6.644491s | 11.915380s | 44.2360% | 3.908941s | 6.058689s |
| 11,653 | 26.515758s | 55.110503s | 51.8862% | 15.048562s | 25.518376s |

CPU comparisons against both direct Rust and the prior adapter individually pass on both workloads. Live-daemon CPU uses procfs ticks; no isolated producer CPU is invented. Cold recovery is one separate warm-OS-cache observation per workload, authenticates prior baseline evidence and genuinely replays selected history checks. State cold close is not separately recorded. Forty-update lifecycle averages establish no general break-even point.

Across40updates, the prior adapter materializes, hashes and rereads636,892,477bytes (original) or2,564,646,194bytes (expanded), derived from exact export lengths and frozen code. State records zero for those full-export operations while consuming4,764/4,795delta bytes. Both already write zero full-export disk bytes because the prior adapter uses sealed memfd.

Median total recipe/materialization phase over40updates falls1.030914→0.007945s (original) and4.267744→0.008541s (expanded). In the state path, persistence remains27.3950%/47.3687%of pooled warm time and the unpartitioned consumer gap17.0160%/22.2097%; genuine selected checking is27.5563%/20.5556%. Promotion is nested inside persistence. These aggregate phases do not separately prove which Python suboperation dominates.

Logical persisted session payload is20,605,642bytes/103,460,296bytes for state versus20,575,155bytes/103,429,809bytes for the prior adapter (medians). It slightly grows; no cache-space reduction is claimed. Shared physical artifact storage and allocated blocks are different quantities. RSS/VmHWM observations are preserved per process; no aggregate peak or memory saving is claimed.

The warm identity contract now uses an authenticated construction-state CAS over verified genesis and exact deltas, not a freshly hashed complete export. The HMAC/source-owner authority, policy, genuine kernel and applicability rule remain. Exact complete-byte reconstruction is checked outside the timed path by independent full witnesses/oracles. The executable bridge is bounded and unproved as a whole. Full-index/applicability loops and cold admission remainO(N); unchanged complex declarations outside the verified prefix remain conservatively checked. No asymptotic or fixed-cone scaling claim is made.

Replay: `python3 frozen-helper/analyze_state.py --summary <recreated-compact>/artifacts/authenticated-state/summary.json --evidence-root <recreated-compact> --expected-source cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5 --ci-run https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/39709067518 --out <fresh-output>`. Original provider packages recreate the exact input; their transport proof is preserved beside this analysis.

The five observed direct genesis-command wall medians are0.288635s(original) and1.351731s(expanded), well below new-session initialization3.908941s/15.048562s. No cold one-shot speedup is claimed. Actual checked-kind counts are independently classified in `work-kind-audit.json`: original early413contains164constructors,120inductive types,122recursors,4quotient obligations,2definitions and1theorem; expanded early672contains283constructors,190inductive types,192recursors,4quotient obligations,2definitions and1theorem. Original unrelated checks1definition; expanded unrelated checks1definition plus119constructors,70inductive types and70recursors. Restorations match. All fifty actual observations per edit agree; ten actual primary receipt cycles were classified against fresh full-index oracle rows.
