# Prospective consequence-accessibility calculus V8

This file freezes predictions before any V8 benchmark outcome is observed.

## State

The accepted developmental prefix is G1 + G2 + G3, where G3 is the V7 `final_field_pi` winner.

The working calculus separates ultimate semantic closure from resource-bounded accessibility. For a representation/runtime grammar G and budget B:

- `C_inf(G)` = consequences/behaviours available in principle;
- `d_G(c)` = cost of realizing consequence c;
- `C_B(G) = {c : d_G(c) <= B}`;
- `E_G,B = intersection of kernels of currently reachable protected consequences`.

A candidate that preserves semantics but transports a fact already available at a producer boundary to a downstream consumer is predicted to leave `C_inf` invariant while reducing `d_G` for affected continuations. It is an accessibility-development candidate. Promotion requires exact semantic equivalence and lower measured cost on both transfer corpora.

## Prospective candidates

All four outcomes below are unmeasured in this composed G1+G2+G3 state at the time of this commit.

| candidate | semantic prediction | accessibility prediction | frozen decision prediction |
|---|---|---|---|
| `g3_param` | unchanged | positive on Std and Cedar | PROMOTE |
| `g3_prior` | unchanged | positive on Std and Cedar | PROMOTE |
| `g3_rigid` | unchanged | positive on Std and Cedar | PROMOTE |
| `g3_all` | unchanged | positive on Std and Cedar | PROMOTE |

The stronger compositional prediction is that `g3_all` remains transfer-positive. No additivity of instruction savings is assumed.

## Falsification

A prediction is counted wrong if the candidate is not byte-identical to the frozen checker output, or if its Callgrind instruction count is not strictly below G3 on either Std or Cedar. `g3_all` going non-positive falsifies the simple compositional accessibility hypothesis even if its components pass individually.

No prediction or threshold is changed after benchmark output is observed.
