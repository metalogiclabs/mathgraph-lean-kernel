# LEAN GROW–DISSOLVE SEARCH V1 — prospective precommit

Status: **FROZEN BEFORE IMPLEMENTATION OR OUTCOME EXECUTION**

## Governing question

Can a compressed, warranted developmental state preserve the future search decisions of the full historical Flash evidence ledger on a real Lean-kernel optimization stream, while requiring less active historical state and less replay work?

This is the real-workload follow-up to the exact finite GROW_DISSOLVE_CYCLE_V1 result.

The tested pattern is:

\[
\boxed{
\text{grow evidence}
\rightarrow
\text{compile warranted residue}
\rightarrow
\text{discard redundant active history}
\rightarrow
\text{continue development}
}
\]

The target is **not** to prove a universal intelligence law. It is to test whether the same grow/dissolve alternation survives in the existing MathGraph Lean-kernel developmental process.

## Frozen repository state

Base branch: qckn-flash-current-v1

Protected semantics:

\[
\boxed{\text{exact Lean Kernel Arena status/stdout parity}}
\]

Current Flash evidence source: experiments/flash_closure_v1_evidence.json

Current capability manifest: experiments/flash_capability_manifest_v1.json

Current full-history controller: experiments/flash_controller_v1.py

The evidence ledger contains 23 causally ordered events at freeze time.

## Frozen retrospective split

The first **13 events** are the developmental past.

Events with zero-based indices 0 through 12 form the training/past prefix.

The remaining **10 events**, indices 13 through 22, are the held-out future stream.

No held-out event may be inspected while compiling the dissolved state at the split.

## Arm A — FULL HISTORY

At each held-out event:

1. append the event to the raw historical ledger;
2. rerun the existing Flash controller from the complete event history;
3. record promoted runtime capability IDs, killed families, capability statuses, ordered frontier, and selected next action.

This is the exact historical-replay arm.

## Arm B — DISSOLVED STATE

At the split, compile the prefix into a reduced developmental state containing only the information required by the frozen controller semantics:

- current capability status per manifest capability;
- dependency graph;
- reject-count / killed-family certificates;
- latest live residual observations needed by frontier construction;
- latest externally verified current authority per capability;
- relevant current performance-rejection state;
- cancelled investigation state;
- ranking metric.

The raw prefix events are then discarded from the active state.

For each held-out event:

1. update the reduced state once;
2. perform dependency/revocation closure;
3. compute the same frontier and selected action from the reduced state;
4. do not replay the discarded historical prefix.

The dissolved controller may retain provenance IDs/hashes, but not the full discarded event payloads.

## Equality target

After **every held-out event**, require exact equality between FULL HISTORY and DISSOLVED STATE for:

\[
\boxed{
(\text{promoted set},
\text{killed families},
\text{selected action})
}
\]

Also record frontier-ID equality and capability-status equality.

## Search-work accounting

Full-history replay work is:

\[
W_{\mathrm{full}}
=
\sum_i |\text{events seen at step }i|.
\]

Dissolved update work counts one event-ingest unit per held-out event, one capability-status/dependency scan unit per manifest capability per held-out event, and one live-summary-key scan unit per frontier computation.

The purpose is not to claim Python wall-clock speedup. It is to test whether active historical replay complexity falls after warranted compilation.

## State-size accounting

At the split record:

- raw prefix event count;
- canonical serialized bytes of the raw prefix ledger;
- canonical serialized bytes of the dissolved active state;
- dissolved/raw state-size ratio.

The dissolved state must be strictly smaller than the raw prefix.

## Real Lean bridge

If both controllers agree on the final selected action, the workflow must connect that decision back to the actual Lean kernel.

### Current-state semantic authority

Build the current branch checker and the frozen semantic baseline commit 74dc5ddb4584e1254f5687615e5b02795b8dc6f3.

Build the pinned Lean Kernel Arena corpus at 510fbfead6f02bed1a0179d01729a6ddf5bfd06d and require exact status/stdout parity on all **409 exports**.

### Selected-action execution

The final selected action is reported, not assumed.

If it is measure_ordinary_unfold_instructions, execute the already-prepared rank gate directly:

- base = current branch;
- candidate = identical source except ORDINARY_UNFOLD_NEUTRAL false -> true;
- exact native PGO using init-prelude;
- verify Mathlib exit-status parity;
- measure Mathlib hardware instructions over 3 alternating A/B replays;
- report whether the candidate improves the Arena ranking metric.

A negative candidate result is scientifically valid and does **not** invalidate the grow/dissolve equivalence result.

If the selected action differs, the workflow records that action and skips this specific Unfold rank gate rather than silently substituting another experiment.

## Frozen gates

LGD1. The evidence ledger contains exactly 23 events and the frozen split is 13/10.

LGD2. The dissolved state is compiled using only prefix events 0..12.

LGD3. Deterministic replay reproduces the dissolved-state certificate and all held-out decisions.

LGD4. FULL HISTORY and DISSOLVED STATE have the same promoted capability set after every held-out event.

LGD5. They have the same killed-family set after every held-out event.

LGD6. They select the same next action after every held-out event.

LGD7. Capability-status maps agree after every held-out event.

LGD8. Frontier action-ID sets agree after every held-out event.

LGD9. The dissolved active state is smaller in canonical serialized bytes than the discarded raw prefix ledger.

LGD10. Dissolved abstract controller work is lower than full-history replay work over the held-out stream.

LGD11. The final selected action is deterministic and explicitly reported.

LGD12. Current checker matches the frozen semantic baseline on all 409 pinned Arena exports.

LGD13. The selected-action execution step is linked to the controller result; no unrelated candidate may be substituted.

LGD14. If the final action is measure_ordinary_unfold_instructions, exact native-PGO Mathlib status parity is required before instruction measurement.

LGD15. Any instruction-rank result is reported as PASS/REJECT independently of semantic equivalence.

LGD16. The result explicitly distinguishes retrospective held-out developmental replay from fresh invention of a new optimization.

## Verdicts

- PASS_LEAN_GROW_DISSOLVE_SEARCH_V1
- PARTIAL_LEAN_GROW_DISSOLVE_SEARCH_V1
- VALID_NEGATIVE_LEAN_GROW_DISSOLVE_SEARCH_V1

The Python developmental replay verdict is determined by LGD1–LGD11 and LGD16.

LGD12–LGD15 are real-Lean qualification/reporting gates performed by CI and recorded separately, because a scientifically valid selected candidate may lose the performance rank gate.

## Claim boundary

A positive result would establish only that, on this frozen real Lean-kernel optimization history, a causally compiled developmental state can preserve the future Flash search decisions of full historical replay while using less active historical state/replay work, and that the resulting current checker remains exact on the pinned Arena corpus.

It would **not** establish autonomous theorem discovery, universal developmental intelligence, or that every future Flash event can always be compressed by the same state schema.

The scientific target is:

\[
\boxed{
\textbf{Can verified Lean development remember the consequence of its history without having to replay the history itself?}
\]
