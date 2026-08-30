universe u v w

/-- Any generated observation that factors through the currently accessible
observation map preserves every equality already induced by that map. -/
theorem generated_observation_preserves_indistinguishability
    {X : Type u} {O : Type v} {Y : Type w}
    (obs : X → O) (f : O → Y) {x y : X}
    (h : obs x = obs y) :
    f (obs x) = f (obs y) := by
  exact congrArg f h

/-- If the verifier distinguishes two states that the complete current
observation signature identifies, no deterministic generated predicate that
uses only that signature can reproduce the verifier on both states. -/
theorem no_separator_without_new_observation
    {X : Type u} {O : Type v}
    (obs : X → O) (verifier : X → Bool) {x y : X}
    (hObs : obs x = obs y) (hVer : verifier x ≠ verifier y) :
    ∀ p : O → Bool,
      ¬ (p (obs x) = verifier x ∧ p (obs y) = verifier y) := by
  intro p hp
  rcases hp with ⟨hx, hy⟩
  have hsame : p (obs x) = p (obs y) := congrArg p hObs
  apply hVer
  calc
    verifier x = p (obs x) := hx.symm
    _ = p (obs y) := hsame
    _ = verifier y := hy

/-- Equivalently: a new consequential separator requires an observation that
strictly refines the old observational equivalence class. -/
theorem new_separator_requires_refinement
    {X : Type u} {O : Type v} {N : Type w}
    (oldObs : X → O) (newObs : X → N) {x y : X}
    (hOld : oldObs x = oldObs y) (hNew : newObs x ≠ newObs y) :
    ∃ a b : X, oldObs a = oldObs b ∧ newObs a ≠ newObs b := by
  exact ⟨x, y, hOld, hNew⟩
