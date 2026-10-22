Actual compact ZIP contextual phase analysis; source d1b22447d23a928ae536cbe838a47fc9682a4b39; CI39679768047.
ZIP SHA256: 878fbeeb4f6241084fd89ca20a2b9b8077c9071e2ada7e2e0b94d054e743d766. Summary SHA256: 198bdc32a8f1b1076394b36b4f9f619b08ab0f9da601ed0a8439c3d84cd1118d.
The helper independently performs exact Decimal arithmetic and does not certify source correctness, HMACs, selected sets or overall qualification. Native REST metadata confirms completed SUCCESS at the exact source; artifact reader is a separate review.

Uninterrupted primary lifecycle: constructor/start + 40 accepted revisions + supported close. Direct arm runs fresh Rust at genesis and every identical accepted revision; arm order alternates. Five paired sequences/profile. Input preparation for direct is outside timing. OS caches are warm.

| Profile | Candidate wall median s | Fresh Rust wall median s | Candidate/direct | Published bootstrap ratio 95% | Candidate CPU median s | Fresh Rust CPU median s |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| original | 8.080982 | 11.371610 | 0.710627843 | [0.599858317, 0.711717443] | 8.078343 | 11.374423 |
| expanded | 33.506680 | 54.792482 | 0.611519659 | [0.545922627, 0.619719776] | 33.563868 | 54.792057 |

Both published wall and CPU economics are SPEEDUP with 5/5 paired wins. Bootstrap intervals above are copied from the actual source report; this analysis adds no new interval.

Same-arm observed start statistics (seconds; these include genesis work):
original: min/median/max 3.669709265000165 / 3.753790549000769 / 3.860264931000529. Update API sum median 3.99397097199835120; constructor/close/compact-recording outer residual median 0.31925751000107980.
expanded: min/median/max 14.625126468999952 / 14.93506536699988 / 15.30674100000033. Update API sum median 17.78802885600271107; constructor/close/compact-recording outer residual median 0.41191029099718393.
These are separate summary medians and must not be added to reconstruct the outer median. Per-sequence exact reconstruction is retained in analysis.json.

Warm edit wall medians (seconds; 50 observations per edit/profile; each arm labeled separately):

| Profile | Edit | Continuous API | Interleaved external apply | Same-input fresh Rust command | Checked/total |
| --- | --- | ---: | ---: | ---: | ---: |
| original | early-definition | 0.112042 | 0.117685 | 0.289584 | 413/3436 |
| original | unrelated-definition | 0.075509 | 0.077851 | 0.288308 | 1/3436 |
| original | restore-early-definition | 0.109156 | 0.114321 | 0.288452 | 413/3436 |
| original | restore-unrelated-definition | 0.074711 | 0.078354 | 0.288166 | 1/3436 |
| expanded | early-definition | 0.499148 | 0.423243 | 1.297726 | 672/11653 |
| expanded | unrelated-definition | 0.472530 | 0.310341 | 1.279427 | 260/11653 |
| expanded | restore-early-definition | 0.507990 | 0.341585 | 1.294441 | 672/11653 |
| expanded | restore-unrelated-definition | 0.307600 | 0.302681 | 1.289284 | 260/11653 |

All 40 published per-revision economic comparisons/profile report SPEEDUP, each based on the actual five interleaved pairs for that revision. The pooled edit medians above are descriptive, not new paired qualification statistics.

Logical cold recovery (one observation/profile, OS caches warm; 40 accepted revisions replayed):
original: constructor/start setup 8.087555673999304 s; observed ready.wall 7.828521862999878 s, including baseline start 3.209461903999909 s and replay/history-chain overhead 4.619059958999969 s; close 0.05494034200000897 s. Setup+close component sum 8.14249601599931297 s. Ready CPU only 7.841831999999982 s.
expanded: constructor/start setup 32.81841754499965 s; observed ready.wall 32.55337208400033 s, including baseline start 12.643617829000505 s and replay/history-chain overhead 19.909754254999825 s; close 0.12054367600012483 s. Setup+close component sum 32.93896122099977483 s. Ready CPU only 32.643269000000146 s.
Independent snapshot/index checks occur between setup and close; the sum is not uninterrupted cold elapsed. Full cold/close CPU is not recorded. Baseline prior evidence is authenticated; accepted revision history is genuinely replayed.

Continuous update phases (median of actual 40-update sequence sums; share uses exact pooled phase sums / exact pooled update API sums):

| Phase | Original median s | Original pooled share | Expanded median s | Expanded pooled share |
| --- | ---: | ---: | ---: | ---: |
| producer_seconds | 0.629953 | 15.864% | 0.718833 | 4.051% |
| baseline_validation_seconds | 0.005211 | 0.131% | 0.005475 | 0.031% |
| identity_update_seconds | 0.081386 | 2.016% | 0.380440 | 2.127% |
| materialization_and_hash_seconds | 1.035638 | 26.014% | 4.028273 | 22.724% |
| checking_seconds | 0.716864 | 18.468% | 2.305915 | 13.009% |
| persistence_seconds | 0.928768 | 23.754% | 7.387411 | 42.999% |
| consumer_unclassified_seconds | 0.529138 | 13.017% | 2.572137 | 14.884% |
| apply_unclassified_seconds | 0.028957 | 0.737% | 0.030911 | 0.175% |

Largest named phase is materialization/hash in all five original sequences and persistence in all five expanded sequences. Expanded consumer unclassified time exceeds checking as a pooled update share. Signed residuals are preserved; no negative continuous residual revisions were observed.
Promotion is nested inside persistence and is not added to the phase table. Its per-sequence sum median is 0.441231111998604319 s original and 3.933872627003438479 s expanded. Residuals include unsplit work; no GC attribution is supported.

Each sequence still materializes/hashes 636,892,477 logical full-export bytes original or 2,564,646,194 expanded, and promotion reads the full successors again. Authenticated delta totals are 4,764/4,795 bytes; zero full-export disk writes excludes memfd movement, baseline IO, and small durable objects.
Interleaved native finish_nanos includes all-component root advancement and full-index cloning, and excludes sparse comparison/serialization/transport/Python reconstruction. It is not pure affected-cone time.
Profiles differ in selected counts (413/1 versus 672/260) as well as declaration/DAG/byte size. These data do not establish constant-cone or asymptotic scaling.
Interleaved post-phase per-process RSS/cumulative VmHWM observations do not establish continuous or aggregate peak memory.
