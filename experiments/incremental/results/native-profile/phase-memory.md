# Native adapter phase memory diagnostic

This separate diagnostic ran after the local qualification benchmark reported CPU quiet. It captures unmodified source and executables from commit `1445e293238abedfb9f0cf727f6c5e17fd685184`, validates the workload manifest and exact qualified export SHA-256 pins for all five cases, and profiles two runs per case. All ten runs preserved the expected classifications and obligation counts: unchanged 0 rechecked / 3,436 reused; early 413 / 3,023; unrelated and leaf 1 / 3,435; invalid REJECTED with rechecked unknown and 3,435 reused.

These are sampled memory observations, not qualification timing or memory-savings evidence. The 2 ms sampler records the Python worker RSS and live descendant RSS separately. A child VmHWM is admitted as post-exec only when `/proc/PID/exe` matches the captured executable. Per-child CPU and raw RSS highwater are also retained from `wait4`.

| Case | Maximum observed worker VmHWM KiB | Native child observed post-exec VmHWM KiB | Selected child observed post-exec VmHWM KiB | Maximum sampled simultaneous RSS sum KiB |
|---|---:|---:|---:|---:|
| unchanged | 61,484 | none launched | none launched | 59,020 |
| early | 59,348 | 97,240 | 86,276 | 130,004 |
| unrelated | 57,472 | 97,272 | 52,452 | 122,328 |
| leaf | 57,472 | 97,236 | 52,420 | 122,296 |
| invalid | 48,136 | 97,272 | 53,472 | 122,332 |

RSS sums count shared pages in each process and do not measure distinct physical memory. Sampling can miss short peaks; observed VmHWM is a cumulative highwater in the new executable, not a resettable phase peak. Parent/child maxima in separate columns need not occur simultaneously. The RSS-sum column is sampled simultaneously.

| Existing wrapped phase | Early worker RSS / live-child RSS KiB | Unrelated worker RSS / live-child RSS KiB |
|---|---:|---:|
| Authenticate prior evidence | 35,436 / 0 | 35,432 / 0 |
| Native parser plus identity | 29,100 / 97,240 | 27,200 / 97,272 |
| Selected kernel | 48,960 / 86,276 | 41,608 / 51,692 |
| Persist checked export | 59,348 / 0 | 57,472 / 0 |
| Persist authenticated receipt | 43,796 / 0 | 41,920 / 0 |

The raw report includes wall time, worker CPU, completed-child CPU, RSS samples, and highwaters for each wrapped call, including file copies/hashes, JSON decoding, and receipt/result encoding. JSON functions can hold the Python GIL long enough to starve the sampler: several decode/encoding phases have no samples, recorded as null. Their phase memory peaks remain unknown. The instrumented timing values are excluded from economics.

Native parsing and identity are interleaved inside one executable and remain one sampled subprocess phase. A separate baseline parse-only invocation observed child post-exec VmHWM 50,632 KiB and CPU 0.015386 s. This is an independent observation; it is not subtracted from native indexing to assert marginal identity work.

The separate parse-only Python launcher observed its own post-exec VmHWM 13,992 KiB while its raw whole-process `wait4` maximum was 60,436 KiB. This illustrates why inherited pre-exec highwater can contaminate launcher/resource maxima. The original paired benchmark RSS numbers, including 267,376 KiB, remain preserved as raw observations and are not used to claim memory savings.

Exact captured engine/native/selected SHA-256 pins are `650aa6f8eb49083ea867d30a85c3aedee1581b605cba7672e15ffc7fe6b1c4c2`, `daca81e13e52edfaa6dacaa7741565f49d1af109dc7ffa23aaea4a6e724137de`, and `da21e6a02048039921bbbc33e935cc37c41d84785782fdb95832bb2936da808f`. Manifest SHA-256 is `bcf2730fd7ac9044ce864ba7f0e9d62acfabaa6c1f79b371962c3235f0e12456`; qualification-pins SHA-256 is `08015efcd86f129fbc8eaa64354825a1e42d331e64daf55ed8a3cbd3a9cb2b82`. Per-case exact export paths and hashes are recorded in [phase-memory.json](phase-memory.json).

Reproduce separately from timing benchmarks:

```bash
python3 experiments/incremental/profile_native_phases.py \
  --workloads /workspace/kernel-audit/workloads-final \
  --checker target/release/check-selected --indexer target/release/export-index \
  --parser target/release/sokonanoda \
  --out /workspace/kernel-audit/native-phase-memory-replay \
  --summary /workspace/kernel-audit/native-phase-memory-replay.json
```

`--out` must be a new directory. CI publishes its raw samples, snapshots, executable captures and summary as artifacts. The unchanged engine creates a temporary issuer key outside that directory and deletes it after collection. No issuer key is copied or published. Final local raw evidence is `/workspace/kernel-audit/native-phase-memory-1445-qualified/`.
