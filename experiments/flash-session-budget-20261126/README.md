# Larger value-session budget experiment

This isolated change raises Flash's existing value budget from 9 MiB to
36 MiB. It preserves the scheduler, declaration-order guards, context keys,
failure handling and all semantic checking. The retained-arena limit stays
four times the budget. It combines none of the other prototypes.

All 39 library tests and retained integration regressions pass, as do
16 raw source-record controls. Two alternating two-worker prefix pairs
accept all 25,131 declarations, and three exact loop controls pass.
Software instructions fall 6.651% overall; the pairs save 6.844% and 6.459%.
This passes the prospective 1% repeat and aggregate cost gate.

This is a CANDIDATE, not a full-input or Arena speed result. The local
230-case portable attempt has 217 correct raw outcomes and 13 SIGKILLs.
A matched original-input control also SIGKILLs the unchanged baseline near
the same 858,000 KiB peak RSS as the candidate. This is consistent with a
local resource constraint, but those processes remain UNKNOWN and their
cause is not established. No signal,
crash or decline is normalized into rejection. The exact rows are retained.

The initial motivation incorrectly called 14,418 census records sessions
or resets. The instrument keeps counters across session clearing and emits
at cache-object destruction; it does not count resets. That statement is
corrected explicitly in protocol-correction.json; it is not evidence of the
candidate's benefit. The measured prefix comparisons provide the cost evidence.

The hosted experiment reconstructs both exact sources and freezes native
and generic executables separately. It checks all 230 exact portable inputs,
then runs two alternating complete Mathlib pairs for native resources and
software instructions. The full prospective memory and cost gates are in
full-protocol.json. Even a passed experiment requires separate coverage of
the other ten large prescribed cases and an independent Arena measurement
before release or ranking claims.

[Hosted full-input qualification](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45811406828) runs source eef92be0975e106aa371d120a3d342af9f597070.
