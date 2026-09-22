# V41R1 — Sustained Nebula ignition, frozen G3 opportunity census

## Why this rerun exists

V41 reached G3 in three independent runs and passed G1, rho2 future
withholding, G2, rho3 future withholding, G3 selection, restart, G1 knockout,
and the G2 semantic-sham control.

The final G3 control failed because it required the *post-intervention* dynamic
opportunity counts in the live and sham arms to be numerically identical.
The real intervention changes later execution enough to perturb that census,
so the comparison was not matched at the measurement boundary.

V41R1 changes only that measurement design. The developmental scripts and
selection rules are inherited byte-for-byte from exact V41 head
`2f670016a71dbc3bfe08216d0495817f66156b7b`.

## Frozen amendment

Before either G3 intervention:

1. build one canonical N2 from one exact pinned `mathgraph` source SHA;
2. run the existing post-G2 probe on a byte-identical copy of that N2;
3. freeze the resulting G3 opportunity count, selected realizer, N2 source
   hash, acquisition-corpus hash, and developmental-script hashes;
4. derive both real and sham G3 arms from byte-identical copies of that same
   canonical N2.

The frozen pre-intervention census is the matched opportunity set. Arm-local
post-intervention opportunity counters are diagnostic only and are not required
to remain equal.

## Unchanged developmental law

No developmental script, selector, materializer, admissibility rule, residual
definition, or semantic gate is changed.

The recurrence remains:

```text
G1 -> (rho2,K2) -> G2 -> (rho3,K3) -> G3
```

under frozen F and frozen D_F.

## Deciding gates

Positive requires all of:

- G1 blind interface genesis passes;
- rho2 future withholding passes;
- G2 unique realizer passes;
- rho3 future withholding passes;
- G3 new pressure and unique realizer pass;
- cold restart reconstructs canonical N2 exactly;
- G1 knockout kills G2;
- G2 semantic sham kills rho3;
- one frozen pre-intervention G3 census is used for both arms;
- real G3 executes positive bypasses at its admitted continuation condition;
- sham G3 executes zero bypasses;
- N2, real G3, and sham G3 are byte-identical on sealed semantic outputs for
  acquisition Std, held-out Std, and held-out Cedar;
- no post-t0 semantic additions occur.

A pass is:

```text
SUSTAINED_NEBULA_IGNITION_V41R1=BOUNDED_POSITIVE
```

This is still a bounded three-generation recurrence claim, not open-ended
self-improvement.
