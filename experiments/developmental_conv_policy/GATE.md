# Frozen V1 gate

The first real Arena-native deciding experiment must satisfy all of the following.

- `SEMANTIC_REGRESSION_COUNT == 0` on the protected accept/reject suite.
- The policy compiler cannot use benchmark names, test IDs, declaration names, or source paths as features.
- Discovery and sealed evaluation workloads are separated before policy fitting.
- At least one generated clause must be behaviorally distinct from the existing short-asymmetric-spine heuristic.
- Aggregate protected cost on the sealed set must improve strictly over frozen K0.
- Exact ablation of the generated policy must remove the measured gain.
- The generated policy must be simpler than a per-instance lookup table under the frozen MDL measure.

Classification on success:

`ARENA_NATIVE_DEVELOPMENTAL_CONVERSION_POLICY_BOUNDED_POSITIVE`

Classification on failure:

Record the sharp residual and do not widen the policy language unless the residual identifies a missing structural distinction.
