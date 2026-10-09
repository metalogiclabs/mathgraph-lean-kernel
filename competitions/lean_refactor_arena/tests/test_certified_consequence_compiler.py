"""Regression tests for future-preserving Lean consequence operator generation."""
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from certified_consequence_compiler import compile_bank, declaration, digest, jsonl


class ConsequenceCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ROOT / "capabilities/reference_em_gauss_derivative_v7.jsonl"
        operators = ROOT / "capabilities/consequence_operator_registry_v1.jsonl"
        cls.sources = jsonl(source)
        cls.operators = jsonl(operators)

    def test_exact_historical_derivative_transport(self):
        bank, report = compile_bank(self.sources, self.operators)
        self.assertEqual(len(bank), 2)
        self.assertEqual(report["controls"], 1)
        self.assertEqual(report["proposals"], 1)
        self.assertEqual(report["exact_prior_certificate_matches"], 1)
        old, new = bank
        self.assertEqual(old["status"], "EXACT_CONTROL_NO_NEW_WARRANT")
        self.assertEqual(new["status"], "CANDIDATE_UNVERIFIED_FOR_NEW_ADMISSION")
        self.assertTrue(new["historical_exact_certificate_match"])
        self.assertEqual(new["historical_run"], 37985510361)
        self.assertEqual(new["proof_sha256"],
                         "cc643e34cf4fa940686b85018ef05099ba1f4f712d9212f4c98c08ef5abab60b")
        self.assertEqual(declaration(old["proof"]), declaration(new["proof"]))
        self.assertEqual(new["required_versions"], ["v4.32.0"])
        self.assertFalse(report["portfolio_mutated"])
        self.assertFalse(report["official_submission"])

    def test_protected_version_change_declines(self):
        rows = deepcopy(self.sources)
        rows[0]["required_versions"] = ["v4.31.0"]
        bank, report = compile_bank(rows, self.operators)
        self.assertEqual(len(bank), 1)
        self.assertEqual(report["declined"][0]["reason"], "PROTECTED_FUTURE_MISMATCH")

    def test_unverified_input_bytes_are_not_implicitly_certified(self):
        rows = deepcopy(self.sources)
        rows[0]["proof"] += "\n  skip"
        bank, report = compile_bank(rows, self.operators)
        self.assertEqual(len(bank), 1)
        self.assertEqual(report["declined"][0]["reason"], "SOURCE_PROOF_HASH_MISMATCH")

    def test_missing_or_ambiguous_anchor_declines(self):
        rules = deepcopy(self.operators)
        rules[0]["anchor_before"] = "obligation_never_present"
        bank, report = compile_bank(self.sources, rules)
        self.assertEqual(len(bank), 1)
        self.assertEqual(report["declined"][0]["reason"],
                         "NON_UNIQUE_OR_ABSENT_OPERATOR_ANCHOR")

    def test_changed_theorem_statement_is_not_admitted(self):
        rule = deepcopy(self.operators[0])
        rule["anchor_before"] = "lemma time_deriv_time_deriv_electricField_of_isExtrema"
        rule["replacement_after"] = "theorem altered_statement"
        bank, report = compile_bank(self.sources, [rule])
        self.assertEqual(len(bank), 1)
        self.assertEqual(report["declined"][0]["reason"], "THEOREM_STATEMENT_CHANGED")

    def test_forbidden_tactic_is_rejected_before_compilation(self):
        rule = deepcopy(self.operators[0])
        rule["replacement_after"] = "by sorry"
        with self.assertRaisesRegex(ValueError, "FORBIDDEN_GENERATED"):
            compile_bank(self.sources, [rule])

    def test_io_and_executable_surface_are_rejected(self):
        for bad in ("IO.println", "run_cmd", "native_decide", "#eval 1"):
            with self.subTest(bad=bad):
                op = deepcopy(self.operators[0])
                op["replacement_after"] = bad
                with self.assertRaisesRegex(ValueError, "FORBIDDEN_GENERATED"):
                    compile_bank(self.sources, [op])

    def test_strata_proof_is_recompiled_exactly_and_not_autopromoted(self):
        source = jsonl(ROOT / "capabilities/reference_strata_subset_v6.jsonl")
        bank, report = compile_bank(source, self.operators)
        self.assertEqual(len(bank), 2)
        self.assertEqual(bank[0]["status"], "EXACT_CONTROL_NO_NEW_WARRANT")
        self.assertEqual(bank[1]["status"], "CANDIDATE_UNVERIFIED_FOR_NEW_ADMISSION")
        self.assertEqual(bank[1]["proof_sha256"],
                         "eebde3bca69669747ab6203723a222fc84c8a6554e188e5f86c00308635a5f13")
        self.assertTrue(bank[1]["historical_exact_certificate_match"])
        self.assertEqual(bank[1]["historical_run"], 37980654973)
        self.assertEqual(bank[1]["required_versions"], ["v4.26.0"])
        self.assertEqual(declaration(bank[0]["proof"]), declaration(bank[1]["proof"]))
        self.assertEqual(report["exact_prior_certificate_matches"], 1)

    def test_two_independent_consequence_families_protect_future_separately(self):
        strata = jsonl(ROOT / "capabilities/reference_strata_subset_v6.jsonl")
        bank, report = compile_bank(self.sources + strata, self.operators)
        self.assertEqual(report["controls"], 2)
        self.assertEqual(report["proposals"], 2)
        self.assertEqual(report["exact_prior_certificate_matches"], 2)
        self.assertEqual(len(bank), 4)
        self.assertFalse(report["portfolio_mutated"])
        self.assertTrue(all(x["status"] == "CANDIDATE_UNVERIFIED_FOR_NEW_ADMISSION"
                            for x in bank if "operator_id" in x))

    def test_duplicate_operator_ids_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OPERATOR_ID"):
            compile_bank(self.sources, self.operators + self.operators)

    def test_no_provenance_when_new_theorem_requested(self):
        rows = deepcopy(self.sources)
        rows[0]["name"] = "AnotherTheorem"
        bank, report = compile_bank(rows, self.operators)
        self.assertEqual(len(bank), 1)
        self.assertEqual(report["proposals"], 0)

    def test_zero_max_candidates_rejected(self):
        with self.assertRaisesRegex(ValueError, "INVALID_CANDIDATE_BUDGET"):
            compile_bank(self.sources, self.operators, max_candidates=0)

    def test_source_hash_and_lean_guard_are_explicit(self):
        op = self.operators[0]
        self.assertEqual(op["source_proof_sha256"], digest(self.sources[0]["proof"]))
        self.assertEqual(op["protected_future"], ["v4.32.0"])
        self.assertEqual(op["verifier_pin"],
                         "aurasoph/lean-refactor@7f3a401470d04f70013d293db4253b088ec8a0ae")


if __name__ == "__main__":
    unittest.main()
