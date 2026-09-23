# V44 — Blind Portable Residual Transfer

## Question

V43 established bounded transfer of the inherited V41R1 capability lineage to
a second, preregistered semantic residual representation.

V44 asks a stricter question:

> If the next residual family is selected *without observing any warm arm*,
> does the inherited K1/K2/K3 lineage still reduce deterministic work on an
> acquisition corpus and avoid reversal on two held-out corpora?

This is a test of **portable developmental capability**, not another
post-hoc hand-picked transfer target.

## Frozen predecessor

V43 source:
`00af28fdd294ed184938c18d280f809e83db29c5`

V43 run:
`35687193098`

V43 artifact:
`10678336569`

V43 artifact digest:
`sha256:683024419d2a64c329f0a2a4c68ca790cc4fc14f5ff2c47fbe73394ff0c78e0f`

V43 verdict:
`NEBULA_TRANSFER_V43=BOUNDED_POSITIVE`

Pinned checker substrate:
`08ddb26718c86213262943ca19ae8cf1b03fa922`

Inherited lineage remains frozen:

```text
K1 = c0 / sort
K2 = c1 / pi
K3 = c3 / pi_continuation
```

No new semantic repair is supplied to a warm arm.

## Blind family generation

The selector runs **only the cold substrate** on **Init.Prelude**.

It observes five generic semantic operation families, each represented only by
the root constructor kind of its input value:

1. `whnf` — input to `whnf_head`;
2. `apply` — function input to `apply`;
3. `projection` — structure input to `do_proj`;
4. `unfold` — input to `unfold_value_go`;
5. `iota` — input to `iota_value`.

The V43 `conv_types_at` family and V42 source-position family are excluded.

For each family, the cold selector records exact counts over the eight semantic
root constructors:

`Rigid, Unfold, Lam, Pi, Sort, NatLit, StrLit, Thunk`.

The selected family is the one with maximum

[
\text{minority-mass}
=
\text{total observations}
-
\text{largest root-kind count}.
]

Ties are resolved by the fixed family order above.

This rule is frozen before any warm arm is executed. The selector output is
written to a sealed JSON record and becomes the only family permitted in the
V44 decision gate.

## Corpora

- selector only: **Init.Prelude**
- acquisition: **Mathlib**
- held-out 1: **Cedar**
- held-out 2: **Std**

The selector never sees Mathlib, Cedar, Std warm-arm measurements.

## Arms

```text
cold     = frozen substrate only
warm12   = substrate + K1 + K2
warm123  = substrate + K1 + K2 + K3
sham123  = substrate + K1 + K2 + semantically inert K3 sham
```

All arms receive identical instrumentation after lineage materialization.

## Primary deterministic cost

The cost remains the exact number of `force_all` invocations required to
complete the full corpus while exposing the selected semantic residual family.

Wall clock is diagnostic only and cannot decide the claim.

## Deciding outcome

`NEBULA_TRANSFER_V44=BOUNDED_PORTABLE_POSITIVE` requires all of:

1. selector produces a non-empty selected family from cold Init.Prelude only;
2. all four arms are byte-identical on Mathlib checker output;
3. all four arms are byte-identical on Cedar checker output;
4. all four arms are byte-identical on Std checker output;
5. the selected family occurs in every arm on every decision corpus;
6. within each corpus, every arm has the same dominant root kind for the
   selected family;
7. `force(warm123) < force(cold)` on Mathlib;
8. at least one inherited generation has a strict Mathlib causal marginal:
   `force(warm12) < force(cold)` or
   `force(warm123) < force(warm12)`;
9. real K3 beats the history-equivalent sham on Mathlib:
   `force(warm123) < force(sham123)`;
10. Cedar does not reverse the inherited advantage:
    `force(warm123) <= force(cold)`;
11. Std does not reverse the inherited advantage:
    `force(warm123) <= force(cold)`.

No V43 threshold is weakened.

## Negative interpretation

A failure is preserved as `NO_PORTABLE_TRANSFER` with the exact selected
family and exact per-arm counts. The family must not be replaced after seeing
the result.

Infrastructure failure before a scientific verdict is not a negative
scientific result.

## Claim boundary

A positive result establishes only bounded portability of one previously
warranted three-generation lineage under one blind residual-selection rule,
one acquisition corpus, and two held-out corpora.

It does not establish universal transfer, unrestricted self-improvement, or
arbitrary capability invention.
