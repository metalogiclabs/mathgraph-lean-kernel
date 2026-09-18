from __future__ import annotations

import json
import unittest
from pathlib import Path

from experiments.qckn_v2_lean_compounding import (
    AuthorityEvidence,
    CompoundingObstruction,
    load_authority,
    run_probe,
)


FIXTURE = Path(__file__).parent / "fixtures" / "passing-authority.json"


class LeanCompoundingAcquisitionTests(unittest.TestCase):
    def test_only_trusted_compiled_present_receives_warm_shortcut(self) -> None:
        result = run_probe(load_authority(FIXTURE))

        self.assertEqual(result.arm("COLD").search_calls, 4)
        self.assertEqual(result.arm("WARM").search_calls, 0)
        self.assertEqual(result.arm("RAW_HISTORY").search_calls, 4)
        self.assertEqual(result.arm("SHAM").search_calls, 4)
        self.assertEqual(result.arm("ANCESTOR_ABLATION").search_calls, 4)
        self.assertEqual(
            {arm.authority_checks for arm in result.arms},
            {4},
        )

    def test_selected_threshold_and_search_unit_are_frozen(self) -> None:
        result = run_probe(load_authority(FIXTURE))

        self.assertEqual(result.selected_threshold, 64)
        self.assertEqual(result.selector_portfolio, (0, 8, 32, 64))
        self.assertEqual(result.search_cost_unit, "selector-candidate-inspected")


class LeanCompoundingPromotionTests(unittest.TestCase):
    def test_dependencies_clear_only_after_external_authority(self) -> None:
        result = run_probe(load_authority(FIXTURE))

        self.assertEqual(
            set(result.dependent.dependencies),
            {
                "lean-r1-context-projector-v1",
                "lean-depth64-selector-v1",
            },
        )
        self.assertEqual(result.standalone.dependencies, ())
        self.assertTrue(result.external_authority_passed)
        self.assertTrue(
            result.standalone.certificate_id.startswith(
                "cert:lean-r1-depth64-authority-v1:"
            )
        )

    def test_heldout_cost_gate_blocks_standalone_identity(self) -> None:
        payload = json.loads(FIXTURE.read_text())
        payload["workloads"]["perf/magma-list-deep-n21"]["ablated_ir"] = 1009
        authority = AuthorityEvidence.from_mapping(payload)

        with self.assertRaises(CompoundingObstruction) as caught:
            run_probe(authority)

        self.assertEqual(caught.exception.code, "HELDOUT_COST_GATE_FAILED")

    def test_semantic_mismatch_blocks_standalone_identity(self) -> None:
        payload = json.loads(FIXTURE.read_text())
        payload["workloads"]["mathlib"]["parity"] = False
        authority = AuthorityEvidence.from_mapping(payload)

        with self.assertRaises(CompoundingObstruction) as caught:
            run_probe(authority)

        self.assertEqual(caught.exception.code, "SEMANTIC_PARITY_FAILED")


class LeanCompoundingRetentionTests(unittest.TestCase):
    def test_reminimisation_preserves_replay_and_moves_parents_to_provenance(self) -> None:
        result = run_probe(load_authority(FIXTURE))

        self.assertEqual(result.retained.decision.active_before_count, 3)
        self.assertEqual(result.retained.decision.active_after_count, 1)
        self.assertEqual(
            result.retained.decision.active_ids,
            ("lean-r1-depth64-standalone-v1",),
        )
        self.assertEqual(result.retained.decision.reserve_ids, ())
        self.assertIn(
            "lean-r1-context-projector-v1",
            result.retained.decision.provenance_ids,
        )
        self.assertIn(
            "lean-depth64-selector-v1",
            result.retained.decision.provenance_ids,
        )
        self.assertEqual(
            result.retained.protected_replay_before,
            result.retained.protected_replay_after,
        )

    def test_restart_is_exact_and_reproduces_warm_with_discovery_disabled(self) -> None:
        result = run_probe(load_authority(FIXTURE))
        restarted = result.retained.present.restart()

        self.assertEqual(restarted.text(), result.retained.present.text())
        self.assertEqual(restarted.digest, result.retained.present.digest)
        self.assertTrue(result.retained.restart_exact)
        self.assertEqual(result.arm("WARM").search_calls, 0)
        self.assertTrue(result.arm("WARM").discovery_disabled)

    def test_declared_selector_recovery_is_reserve_not_active(self) -> None:
        result = run_probe(load_authority(FIXTURE))

        self.assertEqual(
            result.reserve_control.decision.reserve_ids,
            ("lean-depth64-selector-v1",),
        )
        with self.assertRaises(CompoundingObstruction) as caught:
            result.reserve_control.decision.require_removal(
                "lean-depth64-selector-v1"
            )
        self.assertEqual(caught.exception.code, "RecoveryUnavailable")

    def test_metrics_report_the_causal_controls(self) -> None:
        metrics = run_probe(load_authority(FIXTURE)).metrics()

        self.assertTrue(metrics["passed"])
        self.assertEqual(metrics["target_search_calls"]["WARM"], 0)
        self.assertEqual(metrics["target_search_calls"]["COLD"], 4)
        self.assertTrue(metrics["ablation_restores_cold"])
        self.assertEqual(metrics["active_capabilities"], {"before": 3, "after": 1})


if __name__ == "__main__":
    unittest.main()
