# MDA Workload Envelope Convergence V3b — Results

**Verdict:** `VERIFIED_WORKLOAD_ENVELOPE_BIDIRECTIONAL_FRONTIER`

- Run: `34812829051`
- Workflow head: `4e86f6bd217d07e4fc455b1fee3ddc48f93b5807`
- Summary artifact: `10335637011`
- Summary artifact SHA-256: `eb6ff17a229a3b5358a0f6beb24c65809d1944f449970ad867bfb48b7537a256`
- Pinned Arena: `ac1c13762de41b594fa24b90ede8cfd97ac6a765`

## Result

All eight V1 semantically lawful masks reconstructed successfully from both directions and re-established paired source identity.

Under the frozen same-runner workload envelope over `mathlib` and `con-leche`:

- workload-sufficient masks: `[62, 63]`;
- minimum retained capability count: `5`;
- unique minimum frontier: `[62]`.

Therefore:

[
oxed{F_{\mathrm{Mathlib+con\text{-}leche}} = \{62\}}
]

Mask `62 = 0b111110` retains capability bits `1..5` and contracts bit `0`.

## Per-mask workload ratios

Ratios are candidate/full on the same runner.

| Mask | Retained | Mathlib wall | Mathlib CPU | con-leche wall | con-leche CPU | Sufficient |
|---:|---:|---:|---:|---:|---:|---|
| 2 | 1 | 0.959 | 0.957 | 3.115* | 1.846* | no |
| 3 | 2 | 0.954 | 0.954 | 2.901* | 1.913* | no |
| 10 | 2 | 0.926 | 0.923 | 2.539* | 1.903* | no |
| 11 | 3 | 0.944 | 0.945 | 2.562* | 1.883* | no |
| 30 | 4 | 1.418 | 1.443 | 1.548 | 1.557 | no |
| 31 | 5 | 1.201 | 1.218 | 1.210 | 1.340 | no |
| 62 | 5 | 0.984 | 0.990 | 1.002 | 0.999 | **yes** |
| 63 | 6 | 0.994 | 0.999 | 0.985 | 0.985 | **yes** |

`*` controlled timeout: the candidate exceeded the frozen 2.5x-full wall envelope before completion, which already proves failure of the 1.20 wall sufficiency condition.

## Developmental interpretation

The bounded capability class resolves into a staged structure:

[
2 \rightarrow 30 \rightarrow 62
]

where:

- `2` is the minimum semantic kernel;
- `30` carries the wide-representation machinery but incurs substantial workload cost;
- `62` adds the bottom-up wide read-set / one-pass projection compiler and restores both workloads to the full-present envelope;
- bit `0` improves the weaker `30` context but becomes unnecessary once `62` is present.

This is a real contextual-necessity result:

- bit `0` is useful relative to `30`;
- bit `0` is dispensable relative to `62`;
- bits `2..4` alone do not produce an efficient present;
- bit `5` is valuable in the richer context created by those prior capabilities.

## Consequence-boundary result

Mathlib alone favors the much smaller masks `2,3,10,11`.

Con-leche separates those configurations sharply.

Therefore the richer architecture is not justified by semantics or Mathlib alone; it is justified by the enlarged protected consequence set.

## Claim boundary

This result is exact only within:

- the eight V1 semantically lawful masks;
- the frozen Mathlib + con-leche workload pair;
- same-runner wall and CPU ratios;
- the 1.20 acceptance envelope;
- the fixed release build.

It is **not** an official Lean Kernel Arena retired-instruction result and does not establish global checker optimality.
