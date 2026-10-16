import Init

/-!
# A bounded model of dependency-local result reuse

This file proves an abstract model theorem, not correctness of the Rust adapter,
its dependency extraction, its fingerprints, or the Lean kernel. The node space
is finite (`Fin nodeCount`); declarations, environments, meanings, fingerprints,
and checker results remain abstract.

The hypotheses deliberately expose the obligations needed to justify reuse:

* `Local` says that the checker sees only the body's semantic dependencies.
  All relevant transitive reads and metadata must therefore be represented by
  `uses`, or accounted for in the meanings supplied by `interpret`.
* `Complete` says that the supplied dependency list includes every such read.
  It is an assumption about the list, not a proof about an implementation's
  dependency extractor. Extra dependencies are harmless.
* Fingerprints agree for the body and the complete dependency list. A separate,
  explicit adequacy hypothesis says that these particular equal fingerprints
  imply equal declaration inputs. Hash collision freedom is not proved here.
* The two environments interpret each listed dependency's declaration in the
  same way. Kernel version, options, builtin rules, visibility, name lookup,
  and any other context affecting interpretation must satisfy this hypothesis.
* `Deterministic` says that a fresh check has at most one result for a fixed
  body and semantic view. A cached result must already be a valid old result.

No connection between these assumptions and the production implementation is
claimed. In particular, unchanged source text alone does not discharge them.
-/

namespace BoundedReuse

universe uCode uEnvironment uMeaning uFingerprint uResult

/-- A finite collection of declarations together with its interpretation context. -/
structure Snapshot (nodeCount : Nat) (Code : Type uCode)
    (Environment : Type uEnvironment) where
  code : Fin nodeCount → Code
  environment : Environment

/-- The semantic view of all declarations in one snapshot. -/
def view {nodeCount : Nat} {Code : Type uCode}
    {Environment : Type uEnvironment} {Meaning : Type uMeaning}
    (interpret : Environment → Fin nodeCount → Code → Meaning)
    (snapshot : Snapshot nodeCount Code Environment) : Fin nodeCount → Meaning :=
  fun dependency => interpret snapshot.environment dependency (snapshot.code dependency)

/-- Every semantically relevant dependency of the body occurs in the supplied list. -/
def Complete {nodeCount : Nat} {Code : Type uCode}
    (uses : Code → Fin nodeCount → Prop) (body : Code)
    (dependencies : List (Fin nodeCount)) : Prop :=
  ∀ dependency, uses body dependency → dependency ∈ dependencies

/-- Agreement on all dependencies preserves any checker result. -/
def Local {nodeCount : Nat} {Code : Type uCode} {Meaning : Type uMeaning}
    {Result : Type uResult}
    (uses : Code → Fin nodeCount → Prop)
    (checks : Code → (Fin nodeCount → Meaning) → Result → Prop) : Prop :=
  ∀ body oldView newView result,
    (∀ dependency, uses body dependency → oldView dependency = newView dependency) →
    checks body oldView result → checks body newView result

/-- A fixed body and semantic view have at most one checker result. -/
def Deterministic {nodeCount : Nat} {Code : Type uCode} {Meaning : Type uMeaning}
    {Result : Type uResult}
    (checks : Code → (Fin nodeCount → Meaning) → Result → Prop) : Prop :=
  ∀ body semanticView first second,
    checks body semanticView first → checks body semanticView second → first = second

/--
A previously checked result remains valid after an edit, and every fresh result
agrees with it, under explicit locality, completeness, identity, interpretation,
and determinism assumptions. Nodes outside the body and dependency list may
change arbitrarily. Existence of a fresh execution is not asserted: the first
conjunct establishes validity in the relation, while the second establishes
agreement for every fresh result that exists.
-/
theorem reuse_of_unchanged_complete_dependencies
    {nodeCount : Nat} {Code : Type uCode} {Environment : Type uEnvironment}
    {Meaning : Type uMeaning} {Fingerprint : Type uFingerprint} {Result : Type uResult}
    (uses : Code → Fin nodeCount → Prop)
    (checks : Code → (Fin nodeCount → Meaning) → Result → Prop)
    (interpret : Environment → Fin nodeCount → Code → Meaning)
    (fingerprint : Code → Fingerprint)
    (oldSnapshot newSnapshot : Snapshot nodeCount Code Environment)
    (root : Fin nodeCount) (dependencies : List (Fin nodeCount)) (cached : Result)
    (locality : Local uses checks)
    (determinism : Deterministic checks)
    (complete : Complete uses (oldSnapshot.code root) dependencies)
    (unchangedFingerprints : ∀ node, node = root ∨ node ∈ dependencies →
      fingerprint (oldSnapshot.code node) = fingerprint (newSnapshot.code node))
    (fingerprintsIdentifyInputs : ∀ node, node = root ∨ node ∈ dependencies →
      fingerprint (oldSnapshot.code node) = fingerprint (newSnapshot.code node) →
      oldSnapshot.code node = newSnapshot.code node)
    (unchangedInterpretation : ∀ dependency, dependency ∈ dependencies → ∀ declaration,
      interpret oldSnapshot.environment dependency declaration =
        interpret newSnapshot.environment dependency declaration)
    (cachedWasChecked : checks (oldSnapshot.code root) (view interpret oldSnapshot) cached) :
    checks (newSnapshot.code root) (view interpret newSnapshot) cached ∧
      ∀ fresh, checks (newSnapshot.code root) (view interpret newSnapshot) fresh →
        fresh = cached := by
  have sameInput : ∀ node, node = root ∨ node ∈ dependencies →
      oldSnapshot.code node = newSnapshot.code node := by
    intro node relevant
    exact fingerprintsIdentifyInputs node relevant (unchangedFingerprints node relevant)
  have sameRoot : oldSnapshot.code root = newSnapshot.code root :=
    sameInput root (Or.inl rfl)
  have sameDependencyMeanings : ∀ dependency,
      uses (oldSnapshot.code root) dependency →
      view interpret oldSnapshot dependency = view interpret newSnapshot dependency := by
    intro dependency isUsed
    have isListed := complete dependency isUsed
    change interpret oldSnapshot.environment dependency (oldSnapshot.code dependency) =
      interpret newSnapshot.environment dependency (newSnapshot.code dependency)
    calc
      interpret oldSnapshot.environment dependency (oldSnapshot.code dependency) =
          interpret newSnapshot.environment dependency (oldSnapshot.code dependency) :=
        unchangedInterpretation dependency isListed (oldSnapshot.code dependency)
      _ = interpret newSnapshot.environment dependency (newSnapshot.code dependency) :=
        congrArg (interpret newSnapshot.environment dependency)
          (sameInput dependency (Or.inr isListed))
  have reused : checks (newSnapshot.code root) (view interpret newSnapshot) cached := by
    rw [← sameRoot]
    exact locality (oldSnapshot.code root) (view interpret oldSnapshot)
      (view interpret newSnapshot) cached sameDependencyMeanings cachedWasChecked
  exact ⟨reused, fun fresh checked =>
    determinism (newSnapshot.code root) (view interpret newSnapshot) fresh cached checked reused⟩

end BoundedReuse

#print axioms BoundedReuse.reuse_of_unchanged_complete_dependencies
