Retrospective scope: exact source ef434 on research/retained-scc-index-20261016 only. Later parallel retained/SCC, sparse acceptance, session and parser work is outside this review; these findings do not replace or claim priority over it.

Strict independent compact review: **PASS_WITH_STATED_LIMITS**, 25,145 checks and all 14 falsifiers fail closed. Tested source `ef434eb2477fb64d7fd90fdf23f55bd0b35a0243`; run `38961520032`, job `117177490277`. Provider archive SHA256 `685bb4892c3ceb71a0b23da6159712d72885bc76fbfd13907310b5c41ea7cb13`, 37,239,728 bytes, artifact `12075189326`. Actual run/job/required-step success, complete tracked-source Git hashes, five current and four rebuilt qualified449 executable pins/stability logs agree.

CI host: **AMD EPYC 7763**. The earlier449 run used a Xeon8370C despite the same hostname; cross-run absolute timings are not pooled. Qualified449 below is freshly rebuilt and measured beside retained/full on this same host.

| Profile/edit | Retained apply s | Fresh Rust s | Less wall vs Rust | Fresh rebuilt449 s | Less wall vs449 |
|---|---:|---:|---:|---:|---:|
| original/early-definition | 0.233330862 | 0.273052354 | 14.5472% | 0.258597406 | 9.7706% |
| original/unrelated-definition | 0.198308641 | 0.279367364 | 29.0151% | 0.230134132 | 13.8291% |
| expanded/early-definition | 0.882583942 | 1.139220204 | 22.5274% | 0.991732757 | 11.0059% |
| expanded/unrelated-definition | 0.843669542 | 1.144407892 | 26.2789% | 0.955715193 | 11.7237% |

Every warm comparison above wins5/5; every paired bootstrap95% ratio interval lies below1. Expanded early ratios: retained/fresh Rust0.774726378 [0.766978940,0.792577635]; retained/4490.889941303 [0.860238505,0.913786610]. Expanded early CPU medians0.919536s versus1.138889s raw Rust (19.26% less) and1.031062s rebuilt449 (10.82% less). CPU includes adapter, completed children and live daemon tick deltas; direct CPU is completed-child CPU. Tick granularity limits fine comparisons.

Primary early one-update API lifecycle **does not qualify a speedup versus449**: original4.165867169/4.176210830s, ratio0.997523195, interval[0.995712139,1.001035257]; expanded15.377265020/15.438088246s, ratio0.996060184, interval[0.987325238,1.002499055]. These include constructor/startup/apply and supported close as a component sum. Expanded unrelated has a narrow qualified lifecycle ratio0.991816322 [0.985167086,0.995275264]; it does not replace the early primary result. SIGTERM close does not promise graceful Rust EOF/destructor execution.

The complete181-gate matrix has20 paired samples×3arms and40 standalone updates. Independent typed identity, exact sealed composites, authenticated receipt audits and checked/reused partitions agree. Existing197/335/719/251+243/226 suites remain passing;26 adversarial retained fixtures pass; four isolated seven-repetition microbenchmarks preserve complete output parity. The older native whole-file adapter remains NO_SPEEDUP.

Both graph sizes3436→11653 retain the same observed cones: early3declarations/3SCCs/3closure hashes and19dependency edges touched; unrelated1/1/1 and18edges. Standalone whole finish early28.613→29.986µs; core21.971→24.095µs. Standalone complete-index roundtrip still29.777→170.919ms. The seven-repetition isolated expanded early core is22.593µs versus149.523ms full; whole finish28.944µs versus151.391ms. Baseline graph clones/reset are outside isolated timers, with preparation separately measured; this is not total-update scaling.

Largest expanded early retained phase is baseline receipt/export authentication0.220577696s (24.99% of median apply); identity protocol0.193637429s, full receipt persistence0.163806550s, selected checking/full parser0.127679083s, materialization/hash0.109041149s. Ratios of phase medians are descriptive, not additive decomposition. Cold qualified replay remains separate: original setup3.256812941+replay0.250110289s; expanded12.110363531+1.027000791s. No cold-command superiority or continuing-revision amortization is measured.

Sparse storage remains a separate negative: all eight writer/read economic gates NO_SPEEDUP. Expanded20,409,283-byte receipts become300,273-byte early/298,655-byte unrelated capsules; early writer ratio1.03644 and reader2.88384. Both arms still pay original complete acceptance signing/content-ID; sparse additionally scans patches and reconstructs/authenticates the complete original record.44 intended-cause controls pass. Storage capsules authorize no acceptance.

Expanded early retained process post-phase ranges (KiB): adapterRSS166892–308512/HWM347700–347972; producer655400–656928 for both; indexRSS213368–255428/HWM285136–285232. HWM is cumulative startup-inclusive, not a phase peak; no aggregate memory-saving claim.

Remaining boundary: graph-stable closure computation is retained, but complete-index serialization/IPC, baseline authentication/hash, full composite materialization/hash/parser, complete-index receipt and cold preparation remain proportional to total input. Edge changes conservatively use full fallback. The helper ran no kernels, read no omitted full sample/index/cache witnesses, and reauthenticated no historical private HMACs. Each subordinate legacy compact report review lists206 absent raw paths. Full artifact4,210,910,584bytes/provider SHA2fcf3e723403d7c34c8e06604607ec0eb69f5a04f82940bb984db9b0840898f0 was not downloaded; its provider metadata is retained. Separate actual kernel replay evidence must support any stronger replay claim.
