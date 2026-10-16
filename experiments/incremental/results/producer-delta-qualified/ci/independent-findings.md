Independent CI artifact review: PASS WITH STATED LIMITS. Source `4496042c75368f6c35675a9b131c960080afa518`, run `38945728644`, artifact `12067972795`. Archive 4,289,544 bytes, SHA256 `961abb3e6834443dab2cc86eedaf27420c41f52b50d5cbe6c28455ddbd8f2ea5`. The frozen reviewers passed 11,344 checks with zero failures; both report reviews passed all eight falsifiers. Source and binary bindings, 243/243 small and 226/226 expanded gates, 21 controls each, 20 warm samples plus one cold each, retained 197/335/719/251 suites, and compact phase/report bindings agree.

CI host: Intel Xeon Platinum 8370C @ 2.80GHz, Linux 6.17.0-1022-azure. Profiles and local AMD measurements remain separate.

| Profile/edit | Apply wall s | Direct wall s | Wall reduction | Apply CPU s | Direct CPU s | CPU reduction | Bootstrap 95% ratio |
|---|---:|---:|---:|---:|---:|---:|---|
| original/early-definition | 0.281330732 | 0.339654544 | 17.171509% | 0.281954000 | 0.339201000 | 16.877014% | [0.801623236, 0.840696801] |
| original/unrelated-definition | 0.241834543 | 0.347932107 | 30.493755% | 0.240610000 | 0.347719000 | 30.803321% | [0.686730925, 0.773648886] |
| expanded/early-definition | 1.102488122 | 1.415305331 | 22.102454% | 1.149598000 | 1.414997000 | 18.756153% | [0.733268689, 0.827134959] |
| expanded/unrelated-definition | 1.128760262 | 1.428212303 | 20.966914% | 1.157962000 | 1.427895000 | 18.904261% | [0.706129335, 0.814153394] |

All four primary comparisons won 5/5 pairs. Ratios and intervals use paired wall observations with 10,000 bootstrap resamples (seed 20261016). The comparator is fresh full Rust on the same live sealed composite; warm apply includes source verification, producer, authentication, actual full parser, selected kernel checks and persistent receipt. Order is fixed apply then direct; caches are warm. Setup is excluded.

| Profile | Early setup median s | Unrelated setup median s | Cold setup s | Cold outer replay s | Cold direct s |
|---|---:|---:|---:|---:|---:|
| original | 3.879251962 | 3.884775469 | 3.231330245 | 0.300641152 | 0.340516555 |
| expanded | 14.245238111 | 14.260904134 | 11.535685084 | 1.256251774 | 1.400060571 |

Largest early wall phase: small selected checking including full parser 0.065372489 s (23.2369% of the median outer apply); expanded identity/SCC/index finish and IPC 0.334127380 s (30.3067%). Expanded early identity CPU is 0.380927 s (33.1357% of end-to-end median CPU), baseline authentication is 0.237106346 s, full materialization/hash 0.097758634 s, checking 0.181446687 s, persistence 0.179432581 s, producer wall 0.040988647 s. These percentages divide phase medians by total medians; they are descriptive, not an additive decomposition. Identity finish remains largest for expanded unrelated (0.324025163 s, 28.7063%).

The 280-byte expanded early delta still produces a 64,116,034-byte composite and a 20,409,254-byte receipt containing the complete index. Baseline authentication, identity/SCC finish/transfer, full materialization/hash/parser and complete-index receipt remain O(N). One baseline-anchored warm update is qualified; total change-proportional cost and cold/lifecycle superiority remain unknown.

Post-phase per-process samples for early cases (KiB; RSS range / cumulative VmHWM range): small adapter 111596–150836 / 305136–375544; producer 585808–587524 / 585808–587524; index 89424–89480 / 89424–89480. Expanded adapter 336932–540028 / 483252–688676; producer 656072–660756 / 656072–660756; index 177624–245140 / 274760–274896. VmHWM includes startup and is cumulative; these are neither aggregate peaks nor exact phase peaks, and support no memory-saving claim. CPU includes completed children and live producer/index procfs deltas at clock-tick granularity.

Scope: compact review independently checks archive hashes/CRCs/source/binaries, retained reports and publisher projections of checker stdout/counts, evidence IDs and phase fields. The archive omits full sample JSON, raw command outputs/configs and native-index witnesses (206 absent retained raw paths per profile). This review does not reread those omitted witnesses, rerun kernels, or historically reauthenticate HMACs. Earlier local full-file reviews supply separate full-witness evidence. The older full-scan adapter retains its NO_SPEEDUP result.

Machine-readable outputs: `ci-4496042-compact-phases.json`, `ci-small-compact.json`, `ci-expanded-compact.json`, and `ci-4496042-findings.json` in this directory.
