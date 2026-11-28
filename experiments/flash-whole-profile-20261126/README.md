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
