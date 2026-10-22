# Local equal-cone probe: decisive precondition refusal

This is LOCAL EXPLORATORY evidence, not CI qualification, a performance promotion,
or a modification of the qualified implementation. Runtime/source remained
`cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5`; source trees, pinned input trees,
producer, indexer, kernels, cache authority and applicability predicate were not
edited or monkeypatched.

The same existing source-owned theorem was changed in both real workloads:

```lean
theorem leaf (n : Nat) : n = n := Eq.refl n
```

to the distinct valid proof body:

```lean
theorem leaf (n : Nat) : n = n := (fun h : n = n => h) (Eq.refl n)
```

This changes the actual exported proof syntax, rather than merely source text.
Both fresh full indexes establish that declaration names, schedule, global
assumptions and all dependency edges are unchanged. Only the leaf's own and
closure identities change. The native retained transition recomputes one SCC.

| Actual workload | Attempted alternating revisions | Independently selected and actually checked | Reused |
| --- | ---: | ---: | ---: |
| original3436 | 4 | 1 per revision | 3435 |
| expanded11653 | 1 | 260 | 11393 |

Every one of the four original updates was explicitly materialized **after** its
warm timer and checked against a fresh independent full Rust index and full
Rust kernel. The expanded update failed the equal-cone benchmark precondition,
so the driver stopped immediately; five paired scale measurements were not
collected. A separate read-only audit reconstructed that exact accepted input
from its immutable baseline and recorded delta, rebuilt the complete index,
replayed the complete independent applicability partition and ran the fresh
Rust kernel. All agree with the observed selected checker.

The cause of the 259 extra checks is exact and conservative, not dependency
invalidation: 70 unchanged inductive types, 119 unchanged constructors and 70
unchanged recursors occur later in the expanded declaration schedule. Every
one has the actual reason `complex_outside_verified_prefix`. In
`experiments/incremental/engine.py:354`, the first changed declaration ends
prefix reuse. Line355 restricts dependency-local reuse to SIMPLE declarations;
line367 records the reason for other kinds. The fresh full index confirms that
these 259 records, including their own/closure identities and dependencies,
are entirely unchanged. The first is `Std.DHashMap.Raw.Equiv` at index3436.

All seven producer-owned `IncrementalWorkload.*` declarations have indices at
or below3435. Under this existing bounded source producer and applicability
rule, an actual identity-changing local edit therefore cannot supply a
one-obligation selected set in the expanded workload: the later complex
obligations lose their prefix warrant. Changing imported declarations, moving
the schedule, widening complex reuse or inventing a new producer would change
the experiment and was not attempted.

The exact expanded changed input has SHA256
`2093ba3ac4919f0cfbce5769de7181185ddb8c429f4d3fcf36a4529805cb7897`
and64,116,066 bytes. It is preserved losslessly in a content-addressed gzip blob
identified by `negative-audit/summary.json`. Its full-index output and fresh
kernel outputs are also preserved. `audit_negative.py` can reconstruct and
fresh-check the same bytes again; no cache record grants acceptance in that
audit. The observed ephemeral issuer key was deliberately not retained.
Content-address/linkage checks and a fresh full kernel independently establish
the post-run audit boundary; they do not retrospectively reassert HMAC authority.

The single expanded warm interval was0.235303s wall /0.260463s CPU, including
producer, authentication, identity, selected checks and persistence. Native
identity finish was8.972004ms, identity-update wall10.932133ms and persistence
wall126.325425ms. The separate fresh full Rust oracle took1.193775s wall and
the full index775.815684ms. These are isolated exploratory observations with
unequal selected cones and interleaved oracles; **no speedup or scaling claim
is made from them**. Complete raw phase and memory samples are retained.

The source/Cargo closure for selected/index session binaries is byte-identical
from B193 to CEC. The current binary hashes match the observed stable
`benchmark-stable-original-v3/summary.json` manifest. Fresh full oracles use the
independently rebuilt exact-CEC binaries recorded in
`independent-build/build-proof.json`. The stale earlier native manifest was
initially refused before any session started; `preflight-001.json` preserves
that refusal and the later resolved provenance is in the probe summary.

One local observability bug is preserved explicitly: the exploratory driver's
`before` variable was reused for patch text, making its final
`source_closure_unchanged` field falsely compare a string against a hash map.
The original false field was not overwritten. The separate audit compares
the actual complete recorded preflight hash map against all current source
bytes, confirms equality, and records this correction. Pinned inputs and Git
cleanliness checks also pass.

The remaining question exposed here is whether independently justified reuse
can be extended to unchanged complex obligations outside the exact verified
prefix. This probe does not establish that stronger invariant or remove the
remaining whole-index/applicability/decision scans. It supplies no evidence
of asymptotically change-proportional total verification.

Re-run the negative audit locally from the pinned environment:

```sh
python /workspace/kernel-audit/authenticated-state/fixed-cone-probe/audit_negative.py
```

`negative-audit/summary.json` records all259 exact extra withdrawals, actual
full-index partition evidence, exact input identity, pins and fresh kernel
verdict. `summary.json` preserves the stopped exploratory attempt, including
its failed equal-cone precondition. `inventory.json` binds the preserved files.
