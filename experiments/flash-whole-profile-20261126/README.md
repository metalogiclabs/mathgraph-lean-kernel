# Flash — complete instruction result and next cost profile

The [complete diagnostic](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45712976230)
finished on source `bc704eebed4e009bc66af1a849f18315c11f1926` / tree
`06c257f0f2ff1f64711cfa54620b650e6dd59b7e`, using harness `2ba65451`.
Both unchanged full-Mathlib executions accepted 739,167 declarations.

| Frozen executable | Counted application instructions |
| --- | ---: |
| Released Flash baseline | 964,868,458,684 |
| Attributed reconciled candidate | 545,995,448,357 |

Ratio **0.5658755278431343**, a **43.4124% reduction**. Three exact known-loop
calibrations passed. Archive SHA-256/CRC, checker executable hashes, input
identity records, count markers and ratio were independently checked by
`verify_complete_count.py`; raw records are retained in `whole-instructions/`.
This is one complete execution per arm, not a distribution of repeated trials.
It counts application basic-block instructions including libraries. REP-string
and asynchronous-interruption accounting differs from other tools, and loop
calibration does not establish all x86/hardware semantics. **It is not an official
Arena score**, and the published rank is unchanged. No public Arena time is
obtained by multiplying its time by this ratio.

The complementary [bounded native qualification](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45711005244)
found 32.8351% less median CPU and 24.9499% lower observed peak RSS on complete
Mathlib. [Independent reconciliation 795b4ba2](https://github.com/metalogiclabs/mathgraph-lean-kernel/commit/795b4ba255675ca7147d4a23a12574a3c3b1d1b5)
retains its boundaries, 239/240 prescribed outcomes, source-integrity controls,
old-core census and superseded mutual-block prototype. Navier-Stokes/Euler's
pinned export is still being generated at this checkpoint. This candidate is
an attributed Jeremy Chen Apache-2.0 upstream integration with MathGraph
source-correspondence/compatibility repairs; attribution is preserved.

The remaining performance residual calls for a profile of the **reconciled**
core. The old-core census does not establish its costs. `profile_counter.c`
uses the same block-counting rule, but assigns each block at translation to
the containing sized ELF text symbol. Each execution updates one aligned,
atomic 64-bit counter. All counters sum at exit; shared-library/other code and
unmapped main code remain explicit buckets. Inlined work belongs to its
containing compiled symbol. These are exclusive compiled-symbol counts, not
call-tree costs or per-source-function causal attribution.

`prepare.py` accepts only the already-measured candidate binary SHA-256
`09fe7ecf7421be7ad7f7c57596c214bcd6e7c0d912d6d555cb5749b17202bd5b`.
It derives the symbol map and ELF load base from that binary, rejects overlapping
symbol ranges, and records client/map/compiler identities. `run.py` first
requires three exact loop totals and additive symbol counts, then requires
the full pinned input and its complete success count. The unchanged executable
is recovered from artifact 15069518161, without rebuilding the checker. The
full profile has a declared 1,200 s diagnostic budget; resource failure remains
UNKNOWN, never semantic rejection.

The local 25,131-declaration prefix confirms the counter and symbol attribution
run successfully. Its raw comparison with the original unpartitioned counter
is retained under `local-prefix/`; prefix hotspots are **not** promoted to a
full-Mathlib profile. The workflow runs one full candidate profile to locate the
next consequential cost while the last independent coverage gate finishes.

The current Arena adapter (retained blob `06090cd9`) declares two checking
workers and `RUSTFLAGS=-C target-cpu=native`. The completed diagnostic and
frozen profile use one worker and a generic build with AVX-family features
disabled. This is a further reason not to convert their ratios into official
Arena scores. On the exact prefix, the same frozen candidate with two workers
counts 10,572,562,616 vs 10,218,371,992 with one (ratio 1.0346621384). This does
not establish a full-input worker preference or compare native wall time.


## Completed full profile and two rejected continuations

[Run 45717337815](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45717337815)
finished successfully on the exact frozen candidate binary. All 739,167
Mathlib declarations were accepted. Artifact 15070987546, SHA-256
`150792eb39f9807f44cdf22342640350a0e0c4681dc220b4a82e9ae59672ca4d`,
was independently downloaded and CRC/hash checked. Client/source/map/binary
identities, calibration sums, all 731 active symbol buckets and the complete
instruction total were independently reconciled.

| Exclusive compiled routine | Share of counted instructions |
| --- | ---: |
| eval_no_cache | 20.51% |
| eval_node | 13.25% |
| infer_nonvar | 12.70% |
| prune_env_cold | 9.60% |
| intern_frame | 5.12% |

These total **61.18%**. Frontend-named symbols total 6.62%, which is not a
complete parsing-time estimate. The full profiled total is 546,073,810,215,
within 0.0143521% of the preceding unpartitioned candidate count. Inlining
and REP/asynchronous boundaries remain. The costs recur across many
declarations: the old-core finding that the top 100 declarations account for
only about 9% is compatible with concentrated shared evaluation routines.
This convergence motivates representation/cost experiments; it does not
prove a general law or that any selected optimization will improve the whole.

Two original continuations were implemented against the reconciled core,
with tests and two alternating exact-prefix measurement pairs:

- **Compact single-binding ID keys:** 42 library tests and retained source
  controls passed, including changed selected/unused bindings, bound-variable
  type carriers and universe substitutions. Prefix instruction ratio
  **1.000601507541256**: 0.06015% more instructions. REJECTED for performance
  promotion. The older pointer-key negative remains a distinct predecessor.
- **Depth-gated right-spine evaluation:** keeps expression nodes at 32 bytes,
  retains iterative evaluation for deep chains, and allows ordinary memoization
  below depth 64. Forty library tests and retained source controls passed,
  including a typed identity chain across the cutoff and beyond u16 saturation
  at 65,537 applications. Prefix instruction ratio **1.0360025377614008**:
  3.60025% more instructions. REJECTED for performance promotion.

Both failed the predeclared requirement that each pair save at least 1% of
instructions. Neither was sent to broad 230-case or full-Mathlib qualification.
Their patches, plans, test outputs, executable identities and all raw counts
are retained in the adjacent `flash-single-binding-id-20261126` and
`flash-right-spine-depth-20261126` experiment directories. The original test
scaffolding callback-arity error is retained separately; it was repaired before
semantic tests executed. Neither prototype changes the qualified candidate or
published release.

The strongest candidate remains the attributed reconciled core at bc704eeb.
Coverage remains 239/240 pending the one pinned Navier-Stokes/Euler export.
Official Arena instruction/rank improvement remains UNKNOWN. The next useful
performance experiment should distinguish costs inside the closed/open cache
and evaluation paths on the frozen full input before introducing another
lookup or changing evaluation traversal again.


A separately implemented per-thread/private-code-cache profile at run
45718077915 independently completed on the same frozen executable. Its raw
block sums, calibration controls, executable/client identities and all 315
active checker-named symbol totals were checked against this profile; those
315 totals match exactly. This is a crosscheck of instrumentation and an
execution, not a new independent kernel or independent hardware metrology.
The 40,537-row basic-block table is retained as deterministic gzip under
`parallel-basic-block-profile/result/checker-blocks.tsv.gz`, with both raw and
compressed hashes in the adjacent identity record.

Its block detail motivated one additional compiler-hint candidate: inline
`eval_node`, which is entered 948,654,362 times on the full input. Two alternating
prefix pairs passed the predeclared 1% gate (ratio 0.9888404457770111). The isolated
source suite passes 39 library tests and two integration tests, including the
retained source controls; the optional integration test without its external
corpus is not a corpus qualification. All 16 source-metadata controls pass on
the frozen measured binary. Broad local qualification is **UNKNOWN**: the first
portable run was invalidated because a concurrent Cargo test build changed its
executable; the repeated run used the exact read-only measured executable and
recorded 218 matching outcomes plus twelve SIGKILL observations. On the heavy
ITE case, both unchanged baselines and the candidate are SIGKILLed near 854,000
KiB in the current environment. An isolated n7 replay accepts all three. This
supports a local resource boundary, not a semantic rejection or a proved exact
memory limit. The failed compiler/mixed-binary run is preserved and not counted.

The next exact-source workflow freezes executables before Cargo tests, reruns
all 230 portable inputs and 16 source controls sequentially, and compares two
alternating native pairs and two alternating software-instruction pairs on
complete Mathlib. Its predeclared gate also limits native CPU/RSS regression.
That compiler-hint candidate remains unpromoted; its nine other large inputs
and official Arena score remain UNKNOWN. See the adjacent
`flash-eval-dispatch-inline-20261126` experiment for patch, protocol, measured
prefix result, source identity and failed/recovered apparatus lineage.

The separately running joined qualification 45717594082 is for the unchanged
bc704eeb core, not this inlining candidate. Its source/input/binary/verdict joins
must succeed before recording all 240 source-qualified prescribed outcomes.


## Final source qualification and official review update

The final Navier export and source-join workflow have completed. Source bc704eeb
now has **240/240 prescribed outcomes confirmed**, superseding the earlier
239/pending statements above. Both new archives were independently SHA-256/CRC
checked; all case names, input hashes and raw expected verdicts were rejoined,
including the exact 1,559,685,706-byte Navier export and its 129,845 completed
declarations. This is a source-qualified join of separately identified builds,
not an assertion that one frozen executable ran all 240 cases. The retained
manifest contains only prescribed cases; other policy cases are outside it.

[Arena #398](https://github.com/leanprover/lean-kernel-arena/pull/398) is now ready
for review, at unchanged descriptor head 23003362, pinned checker bc704eeb. Its
[official PR run 45722992953](https://github.com/leanprover/lean-kernel-arena/actions/runs/45722992953)
completed SUCCESS in all five jobs. The independently verified official result
and input-stat archives contain **231 selected prescribed cases, all correct**,
plus **28 permitted policy decisions and two policy timeouts (UNKNOWN)**. The
selection is controlled by per-test skip-on-ci flags: it includes 229 of the
230 local portable cases and two larger magma-string inputs. It omits GF3 and
eight other prescribed cases, including Mathlib. The overlapping official and
fork counts must not be added. Official native-build Mathlib hardware scoring
and a new public rank remain unestablished.

The exact final join, Navier, official PR result and official input-stat archives
are retained under `final-verification/`, with hashes and declared boundaries.
The separately qualified attributed core remains the submission. The inlining
hint is outside #398 and is undergoing [full comparison 45723515088](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45723515088):
source tests and the sequential portable-control stage completed; alternating
complete-Mathlib native/software-instruction gates are still running at this
checkpoint. No full-input gain or new 240-case qualification is imputed to it.
