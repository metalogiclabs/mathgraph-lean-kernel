# Source-owned producer probe

`DeltaProducer.lean` is a deliberately bounded producer for the pinned three application
module bodies in `workload/`, imported over a persistent `Std.Data.HashMap` environment.
It reads all four source files on every request. It validates the exact known import
prefixes; `Workload.lean` may contain only its two fixed imports and line comments. The
Python issuer must bind the complete source bytes, toolchain, roots, producer executable,
and request/response files in its authenticated transition receipt. The Lean daemon does
not itself authenticate a receipt or assert a kernel verification result.

The three bodies are concatenated after removing only the validated import prefixes.
This is a workload-specific frontend, not support for arbitrary Lean modules. Real
native probes establish that this representation produces byte-identical exports to
the existing separately compiled pinned workload:

| Snapshot | Full NDJSON SHA-256 |
| --- | --- |
| baseline | `d81ecde8f818ed8d8748b476e22412ec74820a49edbe7986c2c3633a3d66bef0` |
| early definition, 17 to 23 | `13323bf721599b9b77fe0ea94da5c4632edd2a25188842fb09738bfdf74fdd9f` |

Those comparisons include every exported declaration and every serialized DAG row, not
just selected declaration names. The baseline contains 3,436 declarations and 277,321
expression DAG nodes, in 15,922,029 NDJSON bytes. The persistent imported environment has
81,701 constants. Each source request elaborates all seven local declarations from the
same immutable imported environment. It compares every local `ConstantInfo`, checking
both local-name schedules and declaration metadata. Any additional/missing local name,
kind/metadata drift, or replacement of the imported map is rejected. Only safe individual
definitions and theorems with the same metadata schedule are supported.

The daemon keeps the original baseline environment and exporter state for its lifetime.
Each request is relative to that baseline, including requests following another edit or
an error. A changed-name hint must equal the complete actual local declaration comparison.
The hint never determines the comparison's search region. Unchanged imported objects are
the same objects; unchanged local declarations remain represented by the retained baseline
in the consumer overlay, after structural `ConstantInfo` equality has been established.
The candidate elaboration itself allocates new local `ConstantInfo` objects.

The real early edit emits 271 bytes: four new expression DAG rows and one replacement
`early` declaration. Its rows refer to baseline DAG IDs; it is intentionally not a
standalone Lean export. Replacing the old `early` declaration row and adding the four
new nodes was independently parsed by bundled `LeanExport.parseStream`, with exact
`ConstantInfo` equality against all 3,436 declarations of a fresh full export.

Build and exercise the real producer with:

```sh
experiments/incremental/build_delta_producer.sh /tmp/delta-producer-build
python3 experiments/incremental/test_delta_producer.py \
  --binary /tmp/delta-producer-build/delta-producer \
  --output /tmp/delta-producer-evidence
```

The build uses exactly `leanprover/lean4:v4.35.0`, checks its pinned githash, and links the
bundled `LeanExport` native library. `LEAN_SYSROOT` may name an already installed copy of
that exact toolchain. `lean` must be discoverable in the daemon's `PATH` for `findSysroot`.
Compilation to C took about 0.8 seconds and native linking about 0.5 seconds locally.

The CLI starts as `delta-producer INIT.json`. INIT contains `source_files` (the four
path-to-full-text entries), `roots` (the existing nine pinned roots, in export order),
and `baseline_export` (an output path). Its JSON response has `status: ready`.
Subsequent newline-delimited JSON requests contain the full `source_files`, a `delta_path`,
and `expected_changed_names`. Responses use `status: delta` with complete changed names,
DAG growth counts, and phase timings. Errors return `status: error` and do not write a
delta. `op: fresh` plus `source_files` and `export_path` requests an oracle full export;
that operation is separate from timed updates.

A native daemon run on this machine reached ready in 0.820 seconds: import 103 ms,
initial elaboration 39 ms, baseline export 597 ms. Three repeated requests measured
11.4–12.2 ms for complete local elaboration, 28–31 microseconds for complete local
comparison, and 4.4–5.0 ms for delta export. A separate fresh oracle export took 802 ms.
These are individual probe observations, not a statistical benchmark or CI promise.

The delta exporter avoids rebuilding a full typed index, rescanning imported constants,
walking unchanged declaration expressions, and rewriting a full snapshot. Existing
`LeanExport.initState` scans the whole environment to construct its recursor map; the
daemon runs it only during cold initialization, then retains that map. Baseline DAG
hash tables use copy-on-write: restoring the original baseline between requests still
copies shared hash-table backing arrays when inserting new DAG nodes. This is an
O(capacity) memory cost, despite the changed-only emitted rows. The fixed-workload
capacities are smaller than the bundled defaults, but this residual is not eliminated.
Cold start rebuilds all baseline state; no unverified serialized Lean heap is trusted.

The real tests cover pinned full export equality, repeated identical deltas and baseline
reset, no-op requests, changes outside an announced edit hint, duplicate hints, imported
module drift, ignored commands in the root module, local additions/deletions, and kind
drift. The independent full `.olean` import probe also compared all 93,622 declarations:
only `early` differed, but the comparison took about 2.5 seconds and shared no pointer
identities across independent imports. Comparing only the 3,436 published declarations
took about 67 ms. Those approaches retain an O(total) comparison cost and are not the
persistent imported-environment producer implemented here.

This probe does not prove completeness of the Lean frontend, exporter, authentication
issuer, dependency extraction, or checker. It supports this source-owned pinned producer
boundary and records the remaining costs and supported edit restrictions explicitly.

## Opt-in expanded Std profile

`std-hashmap-expanded-v1` preserves the original nine roots as a prefix, then adds the
sorted, unique safe non-internal imported constants under `Std.HashMap.` and
`Std.DHashMap.`. The complete 5,318-root list is retained in `expanded-roots.json`;
`delta-pins.json` pins that file and the five genuine source variants' complete exports.
This adds actual imported library declarations, without generated theorem chains. The
original `pins.json`, original roots, and original source workload remain unchanged.

INIT may specify `profile: "std-hashmap-expanded-v1"` and must provide its complete
explicit root array. The Lean daemon validates the original prefix, extra-root sorting,
uniqueness, canonical names, namespace, membership in the actual pinned imported
environment, and safety. The Python issuer additionally enforces the pinned root-file
hash and exact complete list. The ready receipt returns the actual profile and roots.
The absent-profile default is `original-v1`.

Build the separate larger workload manifest with:

```sh
python3 experiments/incremental/build_delta_workloads.py \
  --workloads /path/to/original-ten-variant-workloads \
  --out /path/to/new-expanded-workloads \
  --producer /tmp/delta-producer-build/delta-producer
```

The builder copies the six source/configuration files for baseline, early definition,
unrelated definition, theorem leaf, and type change. It imports Std once in the producer,
then asks for independent fresh full exports of each source version. Every full export
must match its `delta-pins.json` hash. Those hashes were obtained separately using the
bundled `leanexport` on the original separately compiled `.olean` workload and the exact
expanded root list. All five source-owned exports matched those independent bytes.
The fresh oracle permits same-local-name type/metadata changes; incremental requests
retain their stricter replacement policy. Rejected incremental edits can therefore be
checked through a separate fresh execution.

Expanded snapshots contain 11,653 declarations and 1,089,187 baseline expression DAG
nodes. Baseline and early snapshots each contain 64,115,860 bytes. Their hashes are
`91bfde11f02d7278e4fce3644276ff58e8a32601cfe843f790f8cad6868c0912` and
`60d16dbc287d26de773b90b96cad02c0c0d76cb1db3a91d8ddcb2fbf33bd4edb`.
The early-edit delta contains 280 bytes: the same four nodes and one declaration as the
small case, with longer DAG indices. Three native producer requests took 34.6–39.9 ms
wall time; exporter copying/serialization took 11.5–14.2 ms and source elaboration
11.8–14.0 ms. Cold initialization took 3.10 seconds, including 2.72 seconds to export the
baseline. Three direct Rust full checks on the exact edited snapshot passed in
1.45, 1.50, and 1.53 seconds (about 168–172 MiB peak RSS). These are local probe samples;
consumer verification and authentication costs must be added before comparing complete
warm update paths. Cold initialization and export remain separate amortization costs.

The producer test accepts `--profile std-hashmap-expanded-v1` to run the same exact-byte,
repeatability, no-op, outside-hint, import, schedule, and kind rejection controls against
this larger profile. It does not replace the original-profile tests or qualification.
