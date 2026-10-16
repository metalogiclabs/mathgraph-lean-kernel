# Pinned Python identity profile

The changed-export identity rebuild dominates both tested edits. Each 15,922,029-byte export contains 305,572 NDJSON rows and 3,436 declarations. The Python engine rebuilds the entire typed-DAG identity even when the selected kernel checks one declaration. The SCC pass, authenticated cache read, file copies, and persistence are small relative to row parsing, validation, dependency-set construction, and per-node canonical JSON.

Engine and bounded adapter bytes were extracted from source commit `9ac04033b51703fb135ec3c28621d44b183944fe`; the earlier qualification evidence checkpoint is `a4a7ecbfcd56aa47be894ca0ae1ae657ac5ce606`. Production files were not used as mutable profiling inputs. The engine copy remains byte-identical on disk; optional AST instrumentation is applied only in memory. All three modes produced the same authenticated evidence ID for each edit.

Unprofiled performance evidence uses three fresh processes per edit. Every run gets only the authenticated baseline record and baseline export in its own cache; the changed export and receipt are newly written and fsynced. Cache seeding is outside timing. The operating-system file cache is warm. Process startup includes the same small profiling harness in every run.

| Edit | Rechecked / reused | Wall median s (range) | CPU median s | Maximum RSS KiB | Identity median s | Selected kernel median s |
|---|---:|---:|---:|---:|---:|---:|
| early-definition | 413 / 3023 | 4.3397 (4.2208–4.6516) | 4.3300 | 287,392 | 4.0374 | 0.0551 |
| unrelated-definition | 1 / 3435 | 4.3271 (4.2786–4.3298) | 4.3167 | 286,836 | 4.0555 | 0.0188 |

The selected kernel still parses changed bytes, as required by the qualified unused-node controls. Identity extraction accounts for approximately 93% of total unprofiled wall time here. These runs profile the existing engine; they establish no speedup for a candidate implementation.

Operation attribution below is from the separate instrumented runs. Values are wall / CPU seconds. CPU is Python process time except for the selected kernel row, which uses the child's resource usage. Parent and child rows overlap and must not be summed. The timer wrappers and dependency counters add overhead; their measured values are not unprofiled stage estimates. In particular, exclusive digest time includes Python call/timer overhead as well as SHA-256 and hexadecimal conversion.

| Operation | Calls | Early wall / CPU s | Unrelated wall / CPU s | Pinned source |
|---|---:|---:|---:|---|
| All index rows | 1 | 8.9856 / 8.9825 | 8.7117 / 8.7088 | [source](https://github.com/metalogiclabs/mathgraph-lean-kernel/blob/9ac04033b51703fb135ec3c28621d44b183944fe/experiments/incremental/engine.py#L129) |
| SCC and final summaries | 1 | 0.0952 / 0.0952 | 0.0934 / 0.0934 | [source](https://github.com/metalogiclabs/mathgraph-lean-kernel/blob/9ac04033b51703fb135ec3c28621d44b183944fe/experiments/incremental/engine.py#L210) |
| Strict NDJSON parsing | 305,572 | 1.3423 / 1.3531 | 1.2980 / 1.3084 | [source](https://github.com/metalogiclabs/mathgraph-lean-kernel/blob/9ac04033b51703fb135ec3c28621d44b183944fe/experiments/incremental/engine.py#L131) |
| Per-node canonical JSON | 305,864 | 1.6247 / 1.6356 | 1.5684 / 1.5759 | [source](https://github.com/metalogiclabs/mathgraph-lean-kernel/blob/9ac04033b51703fb135ec3c28621d44b183944fe/experiments/incremental/engine.py#L30) |
| Per-node digest, including canonical JSON | 305,864 | 2.6516 / 2.6539 | 2.5677 / 2.5691 | [source](https://github.com/metalogiclabs/mathgraph-lean-kernel/blob/9ac04033b51703fb135ec3c28621d44b183944fe/experiments/incremental/engine.py#L34) |
| Dependency-set update | 554,856 | 0.3783 / 0.3784 | 0.3742 / 0.3726 | [source](https://github.com/metalogiclabs/mathgraph-lean-kernel/blob/9ac04033b51703fb135ec3c28621d44b183944fe/experiments/incremental/engine.py#L182) |
| Dependency frozenset / sorted list | 280,757 | 0.2148 / 0.2160 | 0.2074 / 0.2086 | [source](https://github.com/metalogiclabs/mathgraph-lean-kernel/blob/9ac04033b51703fb135ec3c28621d44b183944fe/experiments/incremental/engine.py#L189) |
| Cache authentication, including snapshot hash | 1 | 0.0467 / 0.0467 | 0.0482 / 0.0482 | [source](https://github.com/metalogiclabs/mathgraph-lean-kernel/blob/9ac04033b51703fb135ec3c28621d44b183944fe/experiments/incremental/engine.py#L266) |
| Hash source, binary, old and new export bytes | 4 | 0.0241 / 0.0241 | 0.0240 / 0.0240 | [source](https://github.com/metalogiclabs/mathgraph-lean-kernel/blob/9ac04033b51703fb135ec3c28621d44b183944fe/experiments/incremental/engine.py#L38) |
| Copy checker and current export | 2 | 0.0044 / 0.0044 | 0.0046 / 0.0047 | [source](https://github.com/metalogiclabs/mathgraph-lean-kernel/blob/9ac04033b51703fb135ec3c28621d44b183944fe/experiments/incremental/engine.py#L319) |
| New export and receipt persistence | 2 | 0.0129 / 0.0049 | 0.0122 / 0.0039 | [source](https://github.com/metalogiclabs/mathgraph-lean-kernel/blob/9ac04033b51703fb135ec3c28621d44b183944fe/experiments/incremental/engine.py#L285) |
| Canonical JSON outside index | 6 | 0.0655 / 0.0655 | 0.0674 / 0.0674 | [source](https://github.com/metalogiclabs/mathgraph-lean-kernel/blob/9ac04033b51703fb135ec3c28621d44b183944fe/experiments/incremental/engine.py#L408) |
| Selected kernel subprocess | 1 | 0.0605 / 0.0598 | 0.0172 / 0.0152 | [source](https://github.com/metalogiclabs/mathgraph-lean-kernel/blob/9ac04033b51703fb135ec3c28621d44b183944fe/experiments/incremental/engine.py#L389) |

The per-row pass creates 277,321 expression identities and retains 2,607,584 dependency-set members. It consumes 3,301,940 input members in 554,856 set updates. Both edited exports have 25,003 name entries including the anonymous name, 104 level entries including zero, 122 inductive blocks, 48,391 declaration dependency edges, and 3,267 SCCs with at most 16 members. The largest expression and declaration dependency sets have 111 members.

Per-node canonical JSON emits 51,797,432 bytes before hashing, over three times the export byte size; SCC and summary preimages add 3,665,076 bytes. The two file copies move 17,538,757 bytes; four file-hash calls process 33,484,525 bytes. The row phase grows observed RSS from approximately 28,500 KiB to 280,300 KiB. These are boundary RSS samples; the process maximum is measured independently with `wait4`. This profile does not attribute exact allocations to individual data structures.

cProfile independently locates the expensive work in the row loop. The early/unrelated runs spend 2.9531/2.9995 s in 305,574 `json.loads` calls and 7.5429/7.6904 s cumulatively in `make_index`; row validation calls `fields` 305,862 times and `strict_object` 615,334 times. SHA-256 constructors account for only 0.1063/0.1057 s of profiler self time, and hexadecimal conversion 0.1015/0.1043 s. The JSON/Python object pipeline is more expensive than the cryptographic primitive itself.

| Profiler mode | Early wall s / overhead | Unrelated wall s / overhead |
|---|---:|---:|
| cProfile | 7.8867 / 1.82× | 8.0721 / 1.87× |
| Operation instrumentation | 9.4426 / 2.18× | 9.1237 / 2.11× |

The unchanged bounded MathGraph adapter imported the actual unrelated-edit result's 3,436 obligations in 0.2495 s wall / 0.2494 s CPU, with 59,948 KiB maximum RSS. Exact result, evidence, and export pins were supplied externally. Its separate operation run performs 6,875 canonical encodings (0.0741 s), one strict JSON parse (0.0199 s), and two Git provenance subprocesses. cProfile measures its two existing resolver calls at 0.0562 s cumulatively. This adapter remains a bounded caller-qualified import and creates no new receipt authority.

Exact pins and every repetition are retained in [profile.json](profile.json). The profiled engine uses checker SHA-256 `869dbda8a8e2807c194b7937391cc659cfa437fc42bc365d51ec5c8f8cf2009d`, adapter SHA-256 `1937d9504bc44728e57d1a33a0481a6b413fd84d26cca5a929ce7adedd7afa22`, and bounded-adapter SHA-256 `494753602065cfa28adead5518cde834a4753cc7c06344e7505358800e0d8df2`. The workload-manifest SHA-256 is `bcf2730fd7ac9044ce864ba7f0e9d62acfabaa6c1f79b371962c3235f0e12456`. The profiling-tool SHA-256 is `3b12d8476a0427228daee95681687c8bb66197069b968f2fa0837feea8d8c8cb`.

Raw result JSON, metrics, logs, copied harness bytes, isolated caches, and `.prof` files remain outside git in `/workspace/kernel-audit/native-profile-20261016-final/`. The pinned source copy is `/workspace/native-profile-base/`. Earlier exploratory profiling directories were preserved separately and are not the source of the tables above.

Replay with a new external output directory:

```bash
python3 experiments/incremental/profile_identity.py \
  --raw /workspace/kernel-audit/native-profile-replay \
  --summary /workspace/kernel-audit/native-profile-replay-summary.json
```
