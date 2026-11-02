# MathGraph Flash

MathGraph Flash is an experimental Lean export checker **derived from Jeremy Chen's
[sokonanoda](https://github.com/intgrah/sokonanoda)**. It is not an independent
kernel rewrite. Its closure-based conversion algorithm and much of its checking
implementation come from that upstream project, which builds on
[nanoda_lib](https://github.com/ammkrn/nanoda_lib),
[sonanoda](https://github.com/datokrat/sonanoda), and
[still-nanoda](https://github.com/SchrodingerZhu/still-nanoda).

The September Flash lineage includes sokonanoda commit
`28c03d0103e004610e4d47a4828965efb2b70af9`. The review base for the
[bounded soundness draft PR #119](https://github.com/metalogiclabs/mathgraph-lean-kernel/pull/119)
is published Flash `78c7502bac8a5ba000057b3f083bc0595ac65750`.
Independent Nucleus is a separate Rust checker in
[heathsanchez/test, metatron-kernel/](https://github.com/heathsanchez/test/tree/ff003e7fad888d39a40cfd2375885fe20e3209fa/metatron-kernel);
Flash qualification does not establish Nucleus completeness or independence.

## Draft release and verification boundary

The draft repairs imported recursor metadata, exact temporary nested-name
collisions, individual inductive universe scope, closure-context equality, and
zero-field recursor rule typing. Relative to the published Flash base, checking
implementation edits are in `src/conv.rs` and `src/inductive.rs`; native fixture
repairs and CI files are separate review material.

At source `4411234495c92488bdbe15dd6e511addc2d0c439`,
[run #41362223805](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/41362223805)
qualified 45 native tests without exclusions, 128 required valid ACCEPTs,
80 required invalid REJECTs, heavy Magma ACCEPT, and whole Mathlib ACCEPT.
The Arena source was `7e8cc90a3bc1ca827f616d038df13592020c6bf0`;
the full Mathlib export was 6,184,415,052 bytes with SHA256
`22c5de83469408950005589a3bc5ef5157c65549b5a802f85d567c29151306a6`.
The original frozen 196 inputs separately matched all expectations at the same
checking semantics in
[run #41358126978](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/41358126978).

These are source- and input-pinned bounded results, not a universal soundness
proof or a guarantee of compatibility with later exports. This branch remains
a draft: the published Arena checker pin has not been changed. Do not use an
experimental checker as the sole authority for consequential proofs.

## Running and interpreting outcomes

Build with `cargo build --release --locked`; run
`target/release/sokonanoda config.json < input.ndjson`.
The configuration schema and extension behavior are defined in `src/util.rs`.

Preserve the raw process exit and stderr:
0 means ACCEPT, 1 means REJECT at this executable's boundary, and 2 means
DECLINE/UNKNOWN. Exit 1 also covers caught panics and configuration/parser
errors; it is not by itself evidence of a semantic refutation. A timeout,
signal, missing fixture, failed build, or other harness failure must be recorded
as an execution error rather than converted to a checker verdict.
The published Arena wrapper's `|| exit 1` collapses nonzero outcomes and must not
be used as an assurance classifier.

## Performance evidence

Worker count is a latency, CPU, and memory trade-off. Report wall time, user and
system CPU, peak RSS, and hardware retired instructions separately, with source,
input, executable, training, and hardware held fixed. Callgrind counts are
instrumented counts, not hardware retired instructions.

The sparse-clear experiment reduced selected instrumented workloads but failed
to demonstrate a full-Mathlib CPU improvement in
[run #41363240883](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/41363240883).
That optimization is not part of this soundness release. Neither a worker-count
change nor a benchmark position establishes checking originality or an overall
performance win.
