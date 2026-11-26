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

The completed [hosted experiment](https://github.com/metalogiclabs/mathgraph-lean-kernel/actions/runs/45811406828)
passes both declared gates. Independent ZIP SHA-256 and CRC checks, checker
and loop executable hashes, source identities and reconstruction of the raw
metrics agree with the archived reports. All 230 hosted portable cases are
correct; both builds accept all 739,167 declarations in each of four full
Mathlib executions.

On complete Mathlib, software instructions fall **3.006%**, with pair gains
of 3.171% and 2.840%. The native build's median CPU use rises **6.273%**
(133.510 to 141.885 seconds), and peak RSS rises **2.123%**
(4,927,796 to 5,032,404 KiB). The native memory gate passes. The instruction
comparison and native timing use separately identified generic and native
builds; the result does not establish native instruction savings.

This is a WARRANTED bounded experiment, retained as an unpromoted candidate.
The declared gates remain passed; the native CPU regression is an additional
release concern. Nine other large prescribed cases and an independent Arena
measurement remain unqualified. The published release is unchanged. No Arena
seconds are extrapolated from either the prefix or software-counter result.

The original local portable attempt had 217 correct outcomes and 13 SIGKILLs.
A matched control also killed the unchanged baseline near the same peak RSS.
The signal cause remains unknown; the completed hosted 230-case qualification
supersedes that local incompleteness for its native build boundary.

The initial motivation incorrectly called 14,418 census records sessions
or resets. The instrument keeps counters across session clearing and emits
at cache-object destruction; it does not count resets. That statement is
corrected in protocol-correction.json and is not evidence of the candidate's
benefit. Earlier prose also said ten other large cases; the manifest has ten
including Mathlib, leaving nine.

Verified records are in whole-verified/result.json. Reproduce archive and
metric validation with verify_archives.py. Artifact hashes and executable
identities are retained; the 6.3 GB input and compiled counter identities are
runner evidence and were not independently downloaded in this verification.
