#!/usr/bin/env python3
"""Regression tests for theorem-name-free observational consequence routing.

The router is a proposal mechanism only. It cannot warrant a Lean proof or
inherit verification across a changed theorem/environment.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from strategy_hints import route  # noqa: E402


NEW = "OBSERVATIONAL_CONSEQUENCE_TRANSPORT"


class ObservationTransportTests(unittest.TestCase):
    def names(self, statement: str, proof: str) -> list[str]:
        results = route({"statement": statement, "src": statement + " := by\n" + proof})
        self.assertEqual(len({r["strategy"] for r in results}), len(results))
        self.assertLessEqual(len(results), 4)
        return [r["strategy"] for r in results]

    def test_derivative_observation_from_local_equality(self) -> None:
        stmt = "theorem arbitraryWave : deriv (fun x => F x) = deriv (fun x => G x)"
        proof = ("  have hFunction : (fun x => F x) = (fun x => G x) := by ext x; rfl\n"
                 "  rw [Space.deriv_eq, fderiv_fun_sum]\n")
        self.assertIn(NEW, self.names(stmt, proof))

    def test_bilinear_application_observation(self) -> None:
        stmt = "lemma arbitraryGenerators : M a b = N a b"
        proof = ("  have h : M = N := by apply LinearMap.ext\n"
                 "  exact congrArg (fun f => f a b) h")
        self.assertIn(NEW, self.names(stmt, proof))

    def test_linear_map_extensionality_route(self) -> None:
        stmt = "theorem arbitraryLinearObservation : X a = Y a"
        proof = ("  have h := LinearMap.comp_apply\n"
                 "  apply ofCrAnListFBasis.ext\n"
                 "  exact h")
        self.assertIn(NEW, self.names(stmt, proof))

    def test_relation_goal_not_mistaken_for_function_equality(self) -> None:
        stmt = "theorem arbitraryConfluence : Diamond ParallelReduction"
        proof = ("  intro a b c h1 h2\n"
                 "  induction h1\n"
                 "  all_goals grind")
        self.assertNotIn(NEW, self.names(stmt, proof))

    def test_unobserved_equality_not_routed(self) -> None:
        stmt = "theorem arbitraryReflexive (n : Nat) : n = n"
        self.assertNotIn(NEW, self.names(stmt, "  rfl"))

    def test_separating_witness_preserved(self) -> None:
        stmt = "lemma arbitraryZero : f = 0"
        proof = "  intro x\n  have ht : IsTestFunction g := by exact hg"
        names = self.names(stmt, proof)
        self.assertIn("SEPARATING_WITNESS", names)
        self.assertNotIn(NEW, names)

    def test_routing_deterministic_under_same_protected_future(self) -> None:
        stmt = "lemma otherObservation : (D F) = (D G)"
        src = "  have heq : F = G := by assumption\n  exact congrArg D heq"
        self.assertEqual(self.names(stmt, src), self.names(stmt, src))

    def test_strategy_bank_contains_generic_operator_not_solution(self) -> None:
        d = json.loads((ROOT / "strategy_bank_v1.json").read_text(encoding="utf-8"))
        ids = [s["id"] for s in d["strategies"]]
        self.assertEqual(ids.count(NEW), 1)
        self.assertEqual(len(set(ids)), len(ids))
        record = next(s for s in d["strategies"] if s["id"] == NEW)
        self.assertTrue("congrArg" in record["experiment"])
        self.assertTrue("required toolchain" in " ".join(record["protected_future"]))
        # Warm-up names belong to the evidence ledger, not hidden-task routing.
        for name in ("CallElimCorrect", "Electromagnetism.", "Cslib.SKI", "WickAlgebra"):
            self.assertNotIn(name, (ROOT / "strategy_hints.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
