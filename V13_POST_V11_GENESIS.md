# V13 Post-V11 Residual-Derived Genesis

V12 cleanly vetoed all six recycled pre-V11/coarse guards (`NEWLY_ADMISSIBLE_AFTER_V11=0`). V13 therefore does not reuse that candidate family.

Frozen parent state: V11 variant 5, the accepted guard `depth == 5 && flag == Check && idx == 2`.

V13 instruments the post-V11 projection telescope and records only local runtime state: `depth`, `InferFlag`, projection `idx`, `num_params`, loop position `j`, and whether `cur` is already a `Pi`. Std/Cedar identities are used only to compare aggregate trace distributions when prioritizing candidate cells; corpus identity is never visible to the executable patch.

Candidate guards are generated from observed Pi-eligible atomic cells `(depth, flag, idx, num_params, j)`. Each candidate adds a direct-Pi fast path on top of the frozen V11 state and otherwise retains the original `force_all` fallback.

Deciding gates:

1. candidate builds;
2. exact byte-identical outputs versus the V11 baseline on frozen 100k-line Std and Cedar exports;
3. Callgrind delta is strictly negative on both Std and Cedar.

Terminal success marker: `ACCEPTED_POST_V11_GENERATED>0`.

A pass would show that after the V11 residual-derived repair is installed, observing the new developmental state can generate a further executable distinction that is independently verifier-admissible. It would not by itself prove unrestricted open-ended self-improvement.