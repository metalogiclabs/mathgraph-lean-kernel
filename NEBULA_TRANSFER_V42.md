# V42 — Nebula Transfer

## Question

Does the warranted developmental lineage from V41R1 lower the cost of exposing
an independent Lean-kernel residual family, rather than merely sustaining the
same Sort/Pi/Pi-continuation lineage?

The independent target is BVar creation-origin/relevance analysis. This family
predates V41R1 and is not used to construct the V41R1 G1/G2/G3 realizers.

## Frozen source evidence

V41R1 source:
`c9d2d6f868f449e35568d6014b8f45d3094e465a`

V41R1 run:
`35673648421`

V41R1 artifact digest:
`sha256:dd6f021fb5d426189db72135459e2672d74400705e8d9da0ea4060980b45ba40`

Pinned checker substrate inherited from V41R1:
`08ddb26718c86213262943ca19ae8cf1b03fa922`

Inherited developmental products:

```text
K1 = sort interface
K2 = pi interface
K3 = pi_continuation
```

No new semantic repair is supplied to the warm arms.

## Independent target residual

Every arm receives the same instrumentation-only BVar origin census:

- total `force_all` calls;
- BVar producer calls/hits/new allocations;
- creation-origin callsite distribution;
- dominant creation-origin witness.

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
complete the fixed target census on the same corpus.

No wall-clock threshold decides the claim.

## Deciding outcomes

`NEBULA_TRANSFER_V42=BOUNDED_POSITIVE` requires:

1. all four arms are byte-identical on Mathlib checker output;
2. all four arms are byte-identical on held-out Cedar output;
3. every arm exposes the same dominant BVar creation-origin witness;
4. `force(warm123) < force(cold)` on Mathlib;
5. at least one inherited generation has a strict causal marginal:
   `force(warm12) < force(cold)` or
   `force(warm123) < force(warm12)`;
6. K3's semantic arm is strictly better than its history-equivalent sham:
   `force(warm123) < force(sham123)`;
7. held-out Cedar does not reverse the total inherited advantage:
   `force(warm123) <= force(cold)`.

If semantic transfer is exact but the deterministic acquisition-cost gates do
not pass, the result is `NEBULA_TRANSFER_V42=NO_TRANSFER`.

## Claim boundary

A positive result means only that a previously warranted developmental lineage
causally lowers acquisition cost on one independent residual family under a
frozen checker substrate and fixed observation protocol.

It does not establish universal transfer, open-ended self-improvement, or that
every learned developmental product is useful outside its source lineage.
