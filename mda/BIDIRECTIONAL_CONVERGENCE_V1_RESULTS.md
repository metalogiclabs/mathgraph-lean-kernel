# MDA Bidirectional Convergence V1 — Results

**Verdict:** `VERIFIED_BIDIRECTIONAL_SEMANTIC_FRONTIER_CONVERGENCE`

- Hosted run: `34804723050`
- Workflow head: `e80183a6a4568521ee8ebdcd4f7457b588d132f9`
- Summary artifact: `10332633502`
- Summary artifact SHA-256: `013d33b8b1f1e220152c404fdd1513b4513b7605f380f5378972688cbbb90731`
- Pinned Arena: `ac1c13762de41b594fa24b90ede8cfd97ac6a765`

## Result

All 64 frozen capability masks were constructed independently in both directions:

- GENESIS from `16ccc0ed1c28961e411452d1c1a608761d73929e`;
- SOLVENT from `d6a73279e6765e637f9741180cefbd7ef957d8e5`.

The two directions agreed on the classification of **all 64 masks**.

Classification in each direction:

- 8 `LAWFUL`;
- 8 `UNLAWFUL_SEMANTIC_REPLAY`;
- 32 `UNLAWFUL_SOURCE_REPLAY`;
- 16 `UNREACHABLE_PATCH`.

For all 48 masks that produced source payloads in both directions, the normalized executable source payload SHA-256 agreed. There were no lawful masks unique to one direction.

## Minimum semantic frontier

Both directions found minimum retained capability count:

`1`

Both recovered exactly the same frontier:

`mask 2 = 0b000010`

The sole retained atom is:

`2de1895a52d21ad266b77002defe3e6bc69bbcfd — reject underived and orphan recursors`

For mask 2:

- GENESIS applied that soundness capability to the stripped base;
- SOLVENT removed the other five retained atoms from the full present;
- both passed source replay and the frozen Arena fast semantic gate;
- their executable source payloads were byte-identical under the normalized SHA-256 comparison.

The eight lawful masks were identical in both directions:

`[2, 3, 10, 11, 30, 31, 62, 63]`.

## Interaction structure exposed

The frozen class was not a free Boolean cube.

- Masks `32..47` were unreachable in both directions: the bottom-up wide-read-set capability cannot be constructed while omitting required prior wide-environment support.
- 32 configurations failed source/unit replay.
- The 8 reachable source-valid configurations lacking the recursor-soundness atom failed the fixed Arena semantic replay.
- The exact same pattern occurred from genesis and solvent.

This makes the convergence stronger than matching only the endpoint: the two opposite construction paths recovered the same reachability/lawfulness partition throughout the entire frozen 64-cell class.

## Harness correction

The first hosted attempt failed before candidate execution because `SHA256SUMS` contained absolute temporary paths. The only correction was to write relative artifact paths. It changed no candidate, mask, ground, expected outcome or convergence criterion. See `mda/BIDIRECTIONAL_CONVERGENCE_V1_HARNESS_FIX.md`.

## Claim boundary

This result establishes a bounded **semantic-sufficiency** invariant under the five pinned Arena semantic cases plus source/unit replay.

It does **not** say that mask 2 is the best Lean Kernel Arena checker.

The five contracted atoms are principally performance machinery. Arena preference ranks Mathlib performance after correctness, and hosted GitHub runners do not provide the authoritative retired-instruction measurement used by Arena. Therefore:

`semantic minimality != Arena performance optimality`.

The official-performance frontier remains a separate measurement/authority question.
