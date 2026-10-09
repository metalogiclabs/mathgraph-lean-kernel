"""Safety regressions for verified-parent consequence-crossover proposal generation."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import consequence_crossover as cc


FIRST = """theorem demo : Nat = Nat := by
  induction h
  case alpha =>
    exact alpha_left
  all_goals cases h'
  case beta =>
    exact beta_left
  all_goals assumption
"""

SECOND = """theorem demo : Nat = Nat := by
  induction h
  case alpha =>
    exact alpha_right
  all_goals cases h'
  case beta =>
    exact beta_right
  all_goals assumption
"""


class CrossoverTests(unittest.TestCase):
    def test_roundtrip_interleaved_top_level_all_goals(self):
        p = cc.parse(FIRST)
        self.assertEqual(cc.render(p, {}), FIRST)
        self.assertEqual(list(p["chunks"]), ["alpha", "beta"])
        self.assertIn("all_goals cases h'", p["chunks"]["alpha"])
        self.assertEqual(p["footer"], "  all_goals assumption\n")

    def test_inline_case_tactics_are_not_misclassified_as_prelude(self):
        inline = FIRST.replace("  case alpha =>\n    exact alpha_left\n",
                               "  case alpha => exact alpha_left\n")
        p = cc.parse(inline)
        self.assertEqual(list(p["chunks"]), ["alpha", "beta"])
        self.assertEqual(cc.render(p, {}), inline)
        self.assertEqual(p["prefix"], cc.parse(FIRST)["prefix"])

    def test_joins_only_case_consequences_and_preserves_header(self):
        parents = [
            {"name": "demo", "label": "left", "proof": FIRST},
            {"name": "demo", "label": "right", "proof": SECOND},
        ]
        rows = cc.crossover(parents)
        self.assertGreaterEqual(len(rows), 4)
        self.assertEqual(len(rows), len({x["proof_sha256"] for x in rows}))
        controls = [x for x in rows if x["mechanism"] == "EXACT_PARENT_CONTROL"]
        self.assertEqual(len(controls), 2)
        self.assertEqual({x["proof"] for x in controls}, {FIRST, SECOND})
        for row in rows:
            self.assertEqual(row["name"], "demo")
            self.assertTrue(row["proof"].startswith("theorem demo : Nat = Nat := by\n"))
            self.assertEqual(row["proof"].count(" := by\n"), 1)
            self.assertTrue(row["proof_sha256"] == cc.sha256(row["proof"]))
            self.assertNotIn("sorry", row["proof"])

    def test_bad_theorem_or_environment_refused(self):
        with self.assertRaisesRegex(ValueError, "theorem/induction preludes"):
            cc.crossover([
                {"name": "demo", "label": "a", "proof": FIRST},
                {"name": "demo", "label": "b",
                 "proof": SECOND.replace("  induction h", "  induction other")},
            ])
        with self.assertRaisesRegex(ValueError, "identical theorem"):
            cc.crossover([
                {"name": "demo", "label": "a", "proof": FIRST},
                {"name": "other", "label": "b", "proof": SECOND},
            ])

    def test_forbidden_and_ambiguous_case_not_proposed(self):
        with self.assertRaisesRegex(ValueError, "forbidden"):
            cc.parse(FIRST.replace("exact alpha_left", "sorry"))
        with self.assertRaisesRegex(ValueError, "duplicate named case"):
            cc.parse(FIRST.replace("case beta", "case alpha"))

    def test_budget_is_hard_and_deterministic(self):
        parents = [
            {"name": "demo", "label": "left", "proof": FIRST},
            {"name": "demo", "label": "right", "proof": SECOND},
        ]
        a = cc.crossover(parents, max_candidates=3)
        b = cc.crossover(parents, max_candidates=3)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 3)
        with self.assertRaises(ValueError):
            cc.crossover(parents, max_candidates=0)


if __name__ == "__main__":
    unittest.main()
