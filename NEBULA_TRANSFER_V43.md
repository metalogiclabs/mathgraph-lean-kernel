# V43 — Nebula Transfer: Conversion-Root Family

## Question

V42 returned `NO_TRANSFER` because its exact dominant-witness gate failed: the
same BVar-producing logic moved between source line numbers after the inherited
realizers were applied. The deterministic cost results were strongly favorable,
but the preregistered witness criterion is not being reinterpreted after the
fact.

V43 therefore asks a new, preregistered question on a second independent
residual family:

> Does the warranted V41R1 developmental lineage lower the deterministic cost
> of exposing the root-shape distribution of kernel conversion requests?

The target family is conversion-root analysis at `conv_types_at`. It predates
V41R1, is distinct from the V42 BVar creation-origin family, and is not used to
construct the V41R1 G1/G2/G3 realizers.

## Frozen lineage

V41R1 source:
`c9d2d6f868f449e35568d6014b8f45d3094e465a`

V41R1 run:
`35673648421`

V41R1 artifact digest:
`sha256:dd6f021fb5d426189db72135459e2672d74400705e8d9da0ea4060980b45ba40`

V42 source:
`d6b9b6a6b6ee400d1897d8a1b6a71ec1e337d574`

V42 run:
`35683926864`

V42 artifact digest:
`sha256:2ec38425e67c2d010ba72105735a69e96d0e013870781db53ddc7abad0b831ed`

V42 verdict:
`NEBULA_TRANSFER_V42=NO_TRANSFER`

Pinned checker substrate:
`08ddb26718c86213262943ca19ae8cf1b03fa922`

Inherited developmental products:

```text
K1 = sort interface
K2 = pi interface
K3 = pi_continuation
```

No new semantic repair is supplied to the warm arms.

## Independent target residual

Every arm receives the same instrumentation-only census:

- exact total `force_all` calls;
- exact total `conv_types_at` requests;
- frequency distribution of semantic root-shape pairs presented to
  `conv_types_at`;
- dominant semantic root-shape pair.

The witness is a semantic constructor pair such as `Rigid/Rigid` or `Sort/Sort`,
not a source line number. It is fixed before this experiment runs.

The census changes no terminal checker answer. Exact output replay is mandatory.

The acquisition corpus is Mathlib. Cedar is the source-distinct held-out corpus.

## Arms

```text
cold     = frozen substrate only
warm12   = substrate + K1 + K2
warm123  = substrate + K1 + K2 + K3
sham123  = substrate + K1 + K2 + semantically inert K3 sham
```

All four arms are derived from the same exact source SHA.

## Primary deterministic cost

Acquisition cost is the exact number of `force_all` invocations required to
complete the fixed conversion-root census on the same corpus.

No wall-clock threshold decides the claim.

## Deciding outcomes

`NEBULA_TRANSFER_V43=BOUNDED_POSITIVE` requires:

1. all four arms are byte-identical on Mathlib checker output;
2. all four arms are byte-identical on held-out Cedar output;
3. within Mathlib, every arm exposes the same dominant semantic conversion-root
   pair;
4. within Cedar, every arm exposes the same dominant semantic conversion-root
   pair;
5. `force(warm123) < force(cold)` on Mathlib;
6. at least one inherited generation has a strict causal marginal:
   `force(warm12) < force(cold)` or
   `force(warm123) < force(warm12)`;
7. K3's semantic arm is strictly better than its history-equivalent sham:
   `force(warm123) < force(sham123)`;
8. held-out Cedar does not reverse the total inherited advantage:
   `force(warm123) <= force(cold)`.

No V42 threshold is weakened. A negative result remains a negative result.

## Claim boundary

A positive result would establish only bounded cross-family transfer of a
previously warranted developmental lineage to one second independent residual
family under a frozen checker substrate and fixed observation protocol.

It would not establish universal transfer or open-ended self-improvement.
