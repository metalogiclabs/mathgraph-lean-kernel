# Producer-delta residual: source inspection, no new authority

Profiling retains a material full-input cost: the native adapter still spends
roughly 0.17–0.18s on a full typed-DAG scan, and export alone takes roughly 1s
on the primary pinned inputs. Limited source inspection checked what the
installed Lean 4.35.0 exporter already exposes; no producer delta was implemented
or accepted as reuse authority. These observations do not prove that producer
changes are necessary or that further full-scan optimization cannot win.

The existing `LeanExport.dumpEnv` already accepts selected constant names and
exports their dependency closure. `M.run` initializes fresh visited-name,
level, expression and constant tables each invocation. `initState` scans the
environment's constants to construct the inductive/recursor map. Thus selecting
one root is already supported, but it is not an authenticated change delta or a
certificate that omitted declarations are unchanged. Current visited indices
are stream-local intern IDs, not the typed identities qualified here.

Installed source pins from the same release as the pinned exporter binary:

| Installed source | SHA256 |
|---|---|
| LeanExport.lean | `ec95c53d108c5b014e7a53d6b88a4dbe41dc75c2e55102b2f8211268fcb94cf5` |
| LeanExport/Basic.lean | `2e839d4ac1ef1992cfe09c489a97928ad8f8eaea3925bc76b511c6bf85e1b8aa` |
| LeanExport/Parse.lean | `ff46b43893ad39bc8d8b71e2b028b1d7c7065ac11efbeea368d1641419f9460e` |

Relevant inspected locations are `LeanExport.lean:11` (`main`),
`Basic.lean:52` (`State`), `Basic.lean:67` (`M.run`), `Basic.lean:79`
(`initState`), and `Basic.lean:463` (`dumpEnv`). These are installed release
sources; no unverified upstream branch SHA is substituted for their content pins.

Replacing the full export with a selected-root export would not establish the
current whole development, its declaration order, negative name dependencies,
builtin visibility or mutual-inductive boundaries. Such a hint cannot authorize
reuse. A future delta boundary must bind the old accepted environment and the
expected complete new ordered environment, authenticate the unchanged identities
and complete mutations, and retain actual parsing/checking of changed material,
including malformed unused nodes. Authenticating a producer/root establishes
identity under its trust assumptions; it does not prove acceptance, semantic
equivalence or completeness of an unauthenticated delta.

The existing MathGraph dependency-local admission and selected checker can remain
the consumers of such information. For a producer/index route, the missing bridge would be authenticated reusable
identity. Its implementation, independent adequacy and economics remain UNKNOWN;
that route is not established as the smallest or necessary next implementation. Full export construction and
full-byte identity remain separate total-input costs in the implemented system.
