# Qualified native Rust parser vs actual selected checking phase boundary (2026-10-17)

**WARRANTED_BOUNDED diagnostic measurement, not a retained parser or new certificate.** The exact original Rust `Config::to_export_file` parser is timed independently from the real `ExportFile::check_selected_declars` kernel. A separate profiled binary and the unchanged original selected checker perform the same work on identical exact pinned real Lean/Std exports.

- **Exact CI-qualified source** [7a54cc597b8b192141a5a7dffc31546443df1b4b](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/7a54cc597b8b192141a5a7dffc31546443df1b4b).
- [Successful CI #38991829629](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38991829629); source/native test suites, exact pinned original and expanded exports, five paired full and profiled checker runs, fresh full Rust plus C++/paranoid oracles all passed. Original malformed-unused-dag and malformed-unused-typed-node with **zero selected** and invalid-proof with selected theorem were rejected by both authentic parsers. Zero observed wrong acceptance.
- [Portable artifact #12086030282](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38991829629/artifacts/12086030282), independently downloaded archive SHA-256 **bd00e44de78f70cb74c0fc3ba50bb38d383cf7b3726502113fe14183e099c7ec**, equals GitHub-provided digest.

## Five-pair CI medians of separate instrumented phases

| Pin / edit | Exact full parser | Actual selected checking | Parse fraction of intrinsic total |
| --- | ---: | ---: | ---: |
| 3,436 early (413 checked) | 0.017683s | 0.042643s | 28.84% |
| 3,436 unrelated (1 checked) | 0.018799s | 0.002547s | **87.92%** |
| 11,653 early (672 checked) | 0.067577s | 0.076054s | 46.02% |
| 11,653 unrelated (260 checked) | 0.066480s | 0.045960s | **58.84%** |

The previous [red diagnostic CI #38991472575](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/38991472575) passed its actual measurements and negative controls but final report validation wrongly looked for `returncode` instead of the observed `exitcode` in full-oracle summaries. The corrected exact-source run is GREEN. Measurements on different CI hosts cannot be directly subtracted from earlier qualified warm-update timings.

**Consequence:** the next bounded research test should retain and update the real parsed Rust DAG and declaration map under an authenticated changed-only delta. The standard parser currently rejects duplicate declarations and `finish()` consumes the parser; a new one-shot retained-session API must explicitly preserve original simple declaration order and kernel prefix semantics, parse *all* changed bytes including unused malformed nodes, reject any mutation of prior DAG rows or declaration topology, and compare the same changed input against the fresh independent Rust/C++/paranoid checkers. This is a new trusted executable bridge, not a proven general property.

**New isolated candidate launched:** [research/incremental-retained-native-parser-20261017](https://github.com/metalogiclabs/mathgraph-lean-kernel/tree/research/incremental-retained-native-parser-20261017). This is NOT a completed qualification until its own exact-source CI passes.
