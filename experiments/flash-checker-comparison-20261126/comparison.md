# Lean Kernel Arena implementation comparison

All 38 published entries, including MathGraph; 37 other entries. Thirty pinned repository README revisions were retrieved; two pinned repositories return 404 through both connector and public raw URLs. Selected source functions and build adapters were inspected in more depth for the leaders and the official kernel. This is not a full correctness audit of every implementation.

Snapshot: 26 November 2026; Arena source `eee4eeb1672c0a7fa81203f03cc906b8b34657f6`.

## Published performance

[Official Arena](https://arena.lean-lang.org/), retrieved for the pinned snapshot. Time is the Arena instruction-derived virtual time; declines are shown separately from wrong decisions.

| Checker | Correct prescribed | Wrong prescribed | Prescribed declines | Time | Memory |
| --- | ---: | ---: | ---: | ---: | ---: |
| nano-lean | 239 | 0 | 1 | 65.8 s | 5.0 GB |
| gruszka | 240 | 0 | 0 | 76.8 s | 2.6 GB |
| mathgraph | 240 | 0 | 0 | 87.4 s | 4.6 GB |
| sokonanoda | 236 | 0 | 4 | 87.9 s | 5.0 GB |
| rpylean | 238 | 0 | 2 | 96.3 s | 4.4 GB |
| pestka | 240 | 0 | 0 | 4.10 min | 3.5 GB |
| kefir | 240 | 0 | 0 | 7.17 min | 2.5 GB |
| palladium | 234 | 0 | 6 | 7.87 min | 3.8 GB |
| con-ron | 230 | 0 | 10 | 9.65 min | 4.4 GB |
| con-ron-stream | 230 | 0 | 10 | 9.70 min | 3.5 GB |
| kefir-wasm | 240 | 0 | 0 | 9.72 min | 2.7 GB |
| con-agua | 230 | 0 | 10 | 10.9 min | 11.8 GB |
| nanobruijn | 240 | 0 | 0 | 13.1 min | 6.8 GB |
| nanoda | 238 | 0 | 2 | 16.0 min | 5.9 GB |
| con-leche | 229 | 0 | 11 | 17.0 min | 4.8 GB |
| pestka-wasm | 239 | 0 | 1 | 19.0 min | 9.8 GB |
| tenet-jvm | 240 | 0 | 0 | 21.0 min | 12.1 GB |
| official-nightly | 240 | 0 | 0 | 27.3 min | 9.9 GB |
| eink0rn | 236 | 0 | 4 | 29.5 min | 13.4 GB |
| official | 240 | 0 | 0 | 33.7 min | 9.9 GB |
| ind-models | 240 | 0 | 0 | 36.0 min | 6.0 GB |
| kiota | 235 | 0 | 5 | 36.8 min | 6.3 GB |
| tenet | 240 | 0 | 0 | 47.3 min | 11.4 GB |
| tenet-hs | 239 | 0 | 1 | 53.5 min | 11.5 GB |
| ocaml4lean | 237 | 0 | 3 | - | - |
| logos-kernel | 222 | 0 | 18 | - | - |
| evmlean | 186 | 0 | 54 | - | - |
| mini | 177 | 0 | 63 | - | - |
| overfull | 176 | 0 | 64 | - | - |
| lean4lean | 233 | 7 | 0 | 40.3 min | 9.9 GB |
| lean4cobol | 210 | 20 | 10 | - | - |
| canonical-min | 77 | 63 | 100 | - | - |
| nanoclo | 237 | 3 | 0 | 8.37 min | 7.4 GB |
| vow-lean-kernel | 196 | 3 | 41 | - | - |
| metalean-slow | 175 | 3 | 62 | - | - |
| lazylean | 232 | 4 | 4 | - | - |
| metalean-fast | 229 | 5 | 6 | - | - |
| nanoclo-fortran | 232 | 6 | 2 | - | - |

## Implementation inventory

Mechanisms below summarize pinned entry declarations and repository documentation. They are not independent soundness or speed claims. Source availability is explicit.

| Entry | Language | Source review | Main design point |
| --- | --- | --- | --- |
| [canonical-min](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/canonical-min.yaml) | lean | entry and README | Dependent inhabitation/unification solver with a deliberately incomplete export adapter. |
| [con-agua](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/con-agua.yaml) | x86 | entry and README | Assembly generated through a verified compiler; consistency-oriented refinement chain. |
| [con-leche](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/con-leche.yaml) | lean | entry and README | Lean model-based checker with additional checks used by its consistency argument. |
| [con-ron-stream](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/con-ron-stream.yaml) | rust | entry and README | Experimental disk-backed proof storage; retains the con-ron checking core. |
| [con-ron](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/con-ron.yaml) | rust | entry and README | Rust refinement line; compact constructor-specific term columns and two store tiers. |
| [eink0rn](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/eink0rn.yaml) | haskell | entry and README | Haskell checker; body retention and representation choices trade time for memory. |
| [evmlean](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/evmlean.yaml) | solidity | entry and README | Lean checking inside an EVM contract; host/runtime experiment with an incomplete fragment. |
| [gruszka](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/gruszka.yaml) | rust | entry and README | NbE over Susz ids; namespace scheduling, session epochs, direct sort/constant tables. |
| [ind-models](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/ind-models.yaml) | lean | entry and README | Translation validation for inductives; admitted models are checked by Lean. |
| [kefir-wasm](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/kefir-wasm.yaml) | rust | entry and README | Same kefir source under WASI; native/VM performance comparison. |
| [kefir](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/kefir.yaml) | rust | entry and README | Streaming memory-oriented checker; bounded caches and delayed evaluation with fallback. |
| [kiota](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/kiota.yaml) | rust | entry and README | Rust implementation re-deriving recursors; substitution memoization and streamed loading. |
| [lazylean](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/lazylean.yaml) | cpp | entry and README | Reference-style typing over a lazy closure reduction machine in C++. |
| [lean4cobol](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/lean4cobol.yaml) | cobol | entry and README | GnuCOBOL port of lean4lean; streamed input and resource guards. |
| [lean4lean](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/lean4lean.yaml) | lean | entry and README | Lean implementation derived from the official C++ checker. |
| [logos-kernel](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/logos-kernel.yaml) | rust | entry and README | Hash-consed DAG, closure evaluation and projected environments; standalone kernel docs inspected. |
| [mathgraph](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/mathgraph.yaml) | rust | qualified baseline | Attributed sokonanoda core; compact ids, persistent inductive blocks, source-record guards. |
| [metalean-fast](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/metalean-fast.yaml) | lean | entry and README | Verified idealized checker with accelerations; nested inductive filtering limits conformance. |
| [metalean-slow](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/metalean-slow.yaml) | lean | entry and README | Simplicity-focused idealized checker; declines literal accelerations and filters nested inductives. |
| [mini](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/mini.yaml) | lean | entry and README | Small incomplete Lean implementation, useful as a test-suite baseline. |
| [nano-lean](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/nano-lean.yaml) | rust | entry and README | NbE; selective Pi interning, session reuse, contiguous work claims, Init PGO. |
| [nanobruijn](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/nanobruijn.yaml) | rust | entry and README | Pure de Bruijn representation and shift-aware caching. |
| [nanoclo-fortran](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/nanoclo-fortran.yaml) | fortran | entry and README | Fortran translation with integer-id arrays and private OpenMP worker state. |
| [nanoclo](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/nanoclo.yaml) | rust | entry and README | Delayed substitutions, projected closure environments and skew-binary lookup jumps. |
| [nanoda](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/nanoda.yaml) | rust | entry and README | Independent Rust checker in the lineage underlying Flash. |
| [ocaml4lean](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/ocaml4lean.yaml) | ocaml | source returned 404; entry only | Declared OCaml implementation of the reference algorithm; pinned source unavailable. |
| [official-nightly](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/official-nightly.yaml) | cpp | official kernel/entry | Official C++ kernel at the declared nightly toolchain; exact nightly code not audited. |
| [official](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/official.yaml) | cpp | official kernel/entry | Official C++ substitution-based kernel, Lean v4.35.0. |
| [overfull](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/overfull.yaml) | tex | entry and README | Plain TeX checking experiment; not a competitive full-Mathlib speed target. |
| [palladium](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/palladium.yaml) | rust | source returned 404; entry only | Declared typed-local context keys and parallel parsing; pinned source unavailable. |
| [pestka-wasm](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/pestka-wasm.yaml) | aver | entry and README | Same Aver source through wasm-gc; runtime comparison rather than a new kernel algorithm. |
| [pestka](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/pestka.yaml) | aver | entry and README | Substitution checker in Aver; Susz input, proof-position and reduction heuristics. |
| [rpylean](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/rpylean.yaml) | python | entry and README | RPython implementation; JIT and runtime architecture differ from Rust. |
| [sokonanoda](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/sokonanoda.yaml) | rust | entry and README | Closure conversion; the attributed core already integrated into Flash. |
| [tenet-hs](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/tenet-hs.yaml) | haskell | entry and README | Independent Haskell sibling; reference-style algorithm and explicit evidence boundaries. |
| [tenet-jvm](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/tenet-jvm.yaml) | java | entry and README | Independent Java sibling; reference-style inference, reduction and equality. |
| [tenet](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/tenet.yaml) | csharp | entry and README | Independent C# implementation of the reference algorithm; multiple import/checking paths. |
| [vow-lean-kernel](https://github.com/leanprover/lean-kernel-arena/blob/eee4eeb1672c0a7fa81203f03cc906b8b34657f6/checkers/vow-lean-kernel.yaml) | vow | entry and README | Flat index-addressed arenas in Vow; broad checks with resource limitations. |

## Transfer assessment

The published table puts MathGraph third at 87.4 virtual seconds, with all
240 prescribed cases correct. Nano-lean leads at 65.8 seconds and declines
one prescribed case; Gruszka is second at 76.8 seconds with all 240 correct.
The remaining instruction reduction is about 24.7% relative to the current
leader. The scoring rule places speed before declines once wrong outcomes
are tied, so the extra decided case does not itself move MathGraph first.

- **NbE is already present.** Both leaders and Flash use evaluation into
  values/closures. Renaming the existing architecture is not a new speedup.
- **Selective sharing is measurable.** Nano-lean's pinned value interner
  allocates ordinary Pi values without a general interning probe while
  retaining a separately interned Pi path for substitution reuse. Our own
  census identifies inferred Pis as a distinct low-reuse class. The isolated
  Flash test saves 0.844% prefix instructions in aggregate, but the two pairs
  save 1.495% and 0.190%; it fails the prospective 1% repeat gate. It is not
  a complete-input or Arena gain.
- **Direct identity tables differ from another memo layer.** Gruszka uses
  direct level/constant-row tables for some interned values. Flash's failed
  exact-environment front-cache test added a second layer and therefore did
  not test replacing these general interning operations.
- **Demand-directed reduction is the stronger residual.** Gruszka/Pestka
  delay arguments that a selected recursor rule does not need. Flash's bare
  recursor path currently evaluates every argument into a vector before
  choosing a rule. The new isolated recursor-demand prototype investigates
  that ordering while retaining full type inference and source validation.
  Its two alternating prefix pairs save only 0.243% in aggregate (0.651%
  reduction, then 0.165% increase); 40 library tests, 16 raw source controls
  and 29 original recursor tutorials pass. This candidate also fails the
  prospective 1% repeat gate and is not promoted. Full-input effects remain
  UNKNOWN.
- **Worker locality matters.** Nano-lean claims long contiguous ranges that
  shrink near the end. Gruszka groups namespaces and steals contiguous
  ranges. Flash's completed fixed-batch 64-to-512 change saved only 0.836%
  whole-input software instructions; changing the work distribution or
  number of workers needs separate evidence. Gruszka's 8 MiB table budget,
  nano-lean's 64 MiB session budget and Flash's 9 MiB value budget count
  different objects and are not directly interchangeable.
- **Conversion is included.** Gruszka's pinned arena-run packs each NDJSON
  input into a fresh temporary Susz file and then checks it. This adapter
  includes conversion and propagates failure; its public timing is not a
  preconverted-input-only measurement. Its --only mode is not used by the
  Arena command. Nano-lean's persistent --cache option is also absent from
  its Arena command and defaults off.
- **Memory techniques serve a different measured objective.** Kefir and
  con-ron-stream provide useful streaming/storage designs. Their published
  instruction results do not support treating them as the shortest route
  to the present speed lead.
- **Build flags have semantic prerequisites.** Nano-lean uses panic=abort,
  PGO trained on Init and function alignment. Flash classifies semantic
  rejections using caught unwinds; copying panic=abort would alter its
  error contract. Flash's prior Init-PGO trial saved 1.413% full-input
  software instructions and was not promoted. The existing measurement is
  retained rather than rerun merely because another checker uses PGO.
- **Adapters are part of the boundary.** The pinned nanoclo command maps
  every nonzero exit to rejection. Flash keeps raw statuses; a crash or
  decline must not become a semantic rejection through a wrapper.

## New transfer experiments

Each row is an independently authored change tested against the same
qualified Flash source. Gains are generic software-instruction observations
on the exact 25,131-declaration prefix, not full-input or Arena gains.

| Experiment | Aggregate instruction reduction | Pair reductions | Decision |
| --- | ---: | --- | --- |
| Skip interning of inferred Pi closures | 0.844% | 1.495%, 0.190% | Not promoted: repeat gate failed |
| Demand-directed selected recursor prefix | 0.243% | 0.651%, -0.165% | Not promoted: repeat gate failed |
| Direct sort table, complete raw IDs | 0.700% | 0.202%, 1.199% | Not promoted: repeat and aggregate gates failed |

The direct-sort attempt first conflated local and imported universe IDs by
using an index that masks the namespace bit. A retained semantic regression
caught it before speed measurement; a targeted test reproduced it, and the
corrected version preserves complete raw identities. The failed patch is
retained. This repeats the general constraint that shared numeric indices
must not erase distinct namespaces during acceleration.

## Primary source locations inspected more deeply

- [nano-lean value interning](https://github.com/sdiehl/nano-lean/blob/5cd4a25de7cdd8a5fadde3fec53e41a6a8693138/src/value_checker/intern.rs),
  plus scripts/pgo.sh, Cargo.toml, src/fast.rs and
  src/value_checker/{session,value,infer}.rs at the same pin.
- [Gruszka architecture](https://github.com/jasisz/gruszka/blob/39d03331823f084a39323998fb1ee73de374182e/docs/architecture.md),
  scripts/{arena-run,build-pgo.sh}, Cargo.toml, and the interning and
  scheduling routines in src/{tc,main}.rs at the same pin.
- [Pestka](https://github.com/jasisz/pestka/tree/b58afd24297e42fe8ee7f1545ea95aceb7b9d078)
  pinned documentation and Arena adapter.
- [nanoclo](https://github.com/sgraf812/nanoclo/tree/b8cefd0d0c76fe38c1db848e61816e1f23dca79e)
  README's closure and projected-environment design, checked against its
  pinned Arena declaration.
- [official Lean v4.35.0](https://github.com/leanprover/lean4/blob/v4.35.0/src/kernel/type_checker.cpp):
  src/kernel/{type_checker.cpp,expr.h}.
- logos-kernel 1e6ad5b: crates/logicaffeine_kernel/README.md in addition
  to the repository README and Arena entry.

Thirty reachable pinned repository README revisions were read. Palladium
and ocaml4lean returned 404 through both the GitHub connector and the public
raw URLs; their rows remain declaration-only. This comparison claims no
line-by-line correctness audit of the other kernels and promotes no README
performance claim over the official measurements. Mechanisms can inform an
independently authored experiment; each transferred mechanism requires its
own source, correctness and cost evidence on Flash.
