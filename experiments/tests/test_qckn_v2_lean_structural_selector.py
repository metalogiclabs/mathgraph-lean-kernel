from __future__ import annotations

import unittest

from experiments.qckn_v2_lean_structural_selector import (
    CHAIN_THRESHOLDS,
    OBSTRUCTION_CODE,
    StructuralAuthority,
    StructuralDiscovery,
    evaluate_probe,
)


class StructuralDiscoveryTests(unittest.TestCase):
    def test_portfolio_and_cost_semantics_are_frozen(self) -> None:
        discovery = StructuralDiscovery.from_mapping(
            {
                "base8": {"status": 0, "digest": "same", "ir": 1000},
                "chain2": {"status": 0, "digest": "same", "ir": 100},
                "chain4": {"status": 0, "digest": "same", "ir": 150},
                "chain8": {"status": 0, "digest": "same", "ir": 180},
            }
        )

        selected = discovery.select()

        self.assertEqual(CHAIN_THRESHOLDS, (2, 4, 8))
        self.assertEqual(selected.threshold, 8)
        self.assertEqual(selected.search_calls, 3)
        self.assertEqual(selected.cost_unit, "structural-candidate-inspected")

    def test_no_source_qualified_signature_is_exact_obstruction(self) -> None:
        discovery = StructuralDiscovery.from_mapping(
            {
                "base8": {"status": 0, "digest": "same", "ir": 1000},
                "chain2": {"status": 0, "digest": "same", "ir": 1000},
                "chain4": {"status": 0, "digest": "same", "ir": 1000},
                "chain8": {"status": 0, "digest": "same", "ir": 1000},
            }
        )

        result = evaluate_probe(discovery, None)

        self.assertEqual(result.verdict, "RED")
        self.assertEqual(result.first_exact_obstruction, OBSTRUCTION_CODE)
        self.assertIsNone(result.promoted_capability_id)

    def test_semantic_mismatch_cannot_be_reinterpreted_as_cost(self) -> None:
        with self.assertRaisesRegex(ValueError, "exact acceptance/parity"):
            StructuralDiscovery.from_mapping(
                {
                    "base8": {"status": 0, "digest": "same", "ir": 1000},
                    "chain2": {"status": 0, "digest": "same", "ir": 100},
                    "chain4": {"status": 0, "digest": "different", "ir": 200},
                    "chain8": {"status": 0, "digest": "same", "ir": 400},
                }
            )


class StructuralAuthorityTests(unittest.TestCase):
    @staticmethod
    def discovery() -> StructuralDiscovery:
        return StructuralDiscovery.from_mapping(
            {
                "base8": {"status": 0, "digest": "same", "ir": 1000},
                "chain2": {"status": 0, "digest": "same", "ir": 100},
                "chain4": {"status": 0, "digest": "same", "ir": 150},
                "chain8": {"status": 0, "digest": "same", "ir": 180},
            }
        )

    @staticmethod
    def authority(*, magma_candidate: int = 900) -> StructuralAuthority:
        return StructuralAuthority.from_mapping(
            {
                "perf/beta-ladder": {"parity": True, "off_ir": 1000, "candidate_ir": 400},
                "perf/magma-list-deep-n21": {
                    "parity": True,
                    "off_ir": 1000,
                    "candidate_ir": magma_candidate,
                },
                "perf/grind-ring-5": {"parity": True, "off_ir": 1000, "candidate_ir": 1001},
                "mathlib": {"parity": True, "off_ir": 1000, "candidate_ir": 1000},
            }
        )

    def test_identical_authority_promotes_then_reminimises(self) -> None:
        result = evaluate_probe(self.discovery(), self.authority())

        self.assertEqual(result.verdict, "GREEN")
        self.assertEqual(result.selected_threshold, 8)
        self.assertEqual(result.cold_search_calls, 3)
        self.assertEqual(result.warm_search_calls, 0)
        self.assertEqual(result.raw_history_search_calls, 3)
        self.assertEqual(result.sham_search_calls, 3)
        self.assertEqual(result.ablation_search_calls, 3)
        self.assertEqual(result.active_before, 2)
        self.assertEqual(result.active_after, 1)
        self.assertTrue(result.restart_exact)
        self.assertIsNotNone(result.promoted_capability_id)

    def test_heldout_gate_blocks_promotion(self) -> None:
        result = evaluate_probe(
            self.discovery(), self.authority(magma_candidate=995)
        )

        self.assertEqual(result.verdict, "RED")
        self.assertTrue(
            result.first_exact_obstruction.startswith("HELDOUT_COST_GATE_FAILED")
        )
        self.assertIsNone(result.promoted_capability_id)


if __name__ == "__main__":
    unittest.main()
