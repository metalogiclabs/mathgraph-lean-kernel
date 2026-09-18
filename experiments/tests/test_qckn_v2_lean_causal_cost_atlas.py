from __future__ import annotations

import unittest
from pathlib import Path

from experiments.qckn_v2_lean_causal_cost_atlas import (
    ACTIVATION_RETENTION,
    OBSTRUCTION_CODE,
    CausalCostAtlas,
    compile_prior_red,
    load_prior_authority,
    plan_next_search,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "red-depth64-authority-run-35343216790.json"
)


class PriorRedCompilationTests(unittest.TestCase):
    def test_exact_failed_authority_becomes_typed_bounded_obstruction(self) -> None:
        authority = load_prior_authority(FIXTURE)
        compiled = compile_prior_red(authority)

        self.assertEqual(compiled.obstruction.code, OBSTRUCTION_CODE)
        self.assertEqual(compiled.obstruction.selector_threshold, 64)
        self.assertEqual(compiled.obstruction.activation_retention, 0.967984)
        self.assertAlmostEqual(compiled.obstruction.observed_speedup, 1.003369075, places=9)
        self.assertEqual(
            compiled.obstruction.first_exact_obstruction,
            "SOURCE_COST_GATE_FAILED: perf/beta-ladder speedup 1.003369 "
            "is below 2.000000",
        )
        self.assertEqual(compiled.capability.dependencies, ())
        self.assertEqual(
            compiled.capability.execute("ACTIVATION_COUNT_SELECTOR"),
            "RUN_CAUSAL_COST_ATLAS",
        )

    def test_compiled_obstruction_restart_is_exact_and_history_free(self) -> None:
        compiled = compile_prior_red(load_prior_authority(FIXTURE))
        restarted = compiled.present.restart()

        self.assertEqual(restarted.text(), compiled.present.text())
        self.assertEqual(restarted.digest, compiled.present.digest)
        self.assertEqual(
            restarted.capability_graph.active_ids(),
            ("lean-r1-activation-cost-obstruction-v1",),
        )
        self.assertEqual(restarted.meta_memory.episodes, ())

    def test_red_compounds_by_avoiding_repeated_activation_only_search(self) -> None:
        compiled = compile_prior_red(load_prior_authority(FIXTURE))

        cold = plan_next_search(None)
        warm = plan_next_search(compiled.present.restart())
        ablated = plan_next_search(
            compiled.present.revoke_capability(
                compiled.capability.capability_id,
                provenance="red-capital-ablation",
            ).restart()
        )

        self.assertEqual(cold.search_calls, 1)
        self.assertEqual(warm.search_calls, 0)
        self.assertEqual(warm.action, "RUN_CAUSAL_COST_ATLAS")
        self.assertEqual(ablated.search_calls, cold.search_calls)


class CausalCostAtlasTests(unittest.TestCase):
    def test_value_weighted_atlas_confirms_activation_cost_mismatch(self) -> None:
        atlas = CausalCostAtlas.from_mapping(
            {
                "off": {"status": 0, "parity_digest": "same", "callgrind_ir": 1000},
                "0": {"status": 0, "parity_digest": "same", "callgrind_ir": 100},
                "8": {"status": 0, "parity_digest": "same", "callgrind_ir": 200},
                "32": {"status": 0, "parity_digest": "same", "callgrind_ir": 800},
                "64": {"status": 0, "parity_digest": "same", "callgrind_ir": 997},
            }
        )

        result = atlas.analyse()

        self.assertEqual(result.verdict, "OBSTRUCTION_CONFIRMED")
        self.assertAlmostEqual(result.rows[64].activation_retention, ACTIVATION_RETENTION[64])
        self.assertAlmostEqual(result.rows[64].causal_savings_retention, 3 / 900)
        self.assertAlmostEqual(result.rows[64].speedup, 1000 / 997)

    def test_semantic_or_acceptance_mismatch_is_not_reinterpreted_as_cost(self) -> None:
        payload = {
            "off": {"status": 0, "parity_digest": "same", "callgrind_ir": 1000},
            "0": {"status": 0, "parity_digest": "same", "callgrind_ir": 100},
            "8": {"status": 0, "parity_digest": "same", "callgrind_ir": 200},
            "32": {"status": 0, "parity_digest": "same", "callgrind_ir": 800},
            "64": {"status": 1, "parity_digest": "different", "callgrind_ir": 997},
        }

        with self.assertRaisesRegex(ValueError, "exact acceptance/parity"):
            CausalCostAtlas.from_mapping(payload)

    def test_failure_to_reproduce_prior_red_is_a_red_gate(self) -> None:
        atlas = CausalCostAtlas.from_mapping(
            {
                "off": {"status": 0, "parity_digest": "same", "callgrind_ir": 1000},
                "0": {"status": 0, "parity_digest": "same", "callgrind_ir": 100},
                "8": {"status": 0, "parity_digest": "same", "callgrind_ir": 101},
                "32": {"status": 0, "parity_digest": "same", "callgrind_ir": 102},
                "64": {"status": 0, "parity_digest": "same", "callgrind_ir": 103},
            }
        )

        self.assertEqual(atlas.analyse().verdict, "PRIOR_RED_NOT_REPRODUCED")


if __name__ == "__main__":
    unittest.main()
