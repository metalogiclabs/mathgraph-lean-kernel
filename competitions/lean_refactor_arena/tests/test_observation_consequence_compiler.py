"""Fail-closed tests for generic source-exact observational consequence synthesis."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from observation_consequence_compiler import compile_candidates, digest, main  # noqa: E402


PROOF = """theorem sampleObservation {X : Type} (f g : X → Nat) (x : X)
    (h : f = g) : f x = g x := by
  have heq : f = g := h
  have target : f x = g x := by
    calc
      f x = g x := by rw [heq]
  exact target
"""
OLD_SITE = """  have target : f x = g x := by
    calc
      f x = g x := by rw [heq]
"""
SPEC = {
    "schema": "mathgraph.lra.observation-transfer-input.v1",
    "name": "Sample.sampleObservation",
    "parent_sha256": digest(PROOF),
    "exact_site": OLD_SITE,
    "goal_prefix": "  have target : f x = g x := by\n",
    "equality_name": "heq",
    "observers": [
        {"id": "inferred", "term": "(fun z => z x)"},
        {"id": "typed", "term": "(fun z : X → Nat => z x)"},
    ],
    "rewrites": [
        {"id": "direct", "tactics": []},
        {"id": "refl_norm", "tactics": ["simpa only [] using observed_witness"]},
    ],
}
PARENT = {"name": SPEC["name"], "label": "control", "proof": PROOF}


class ConsequenceCompilerTests(unittest.TestCase):
    def candidates(self, spec=SPEC, parent=PARENT, limit=24):
        return compile_candidates(parent, spec, limit=limit)

    def test_warranted_control_preserved_without_reformatting(self):
        rows = self.candidates()
        self.assertEqual(rows[0]["proof"], PROOF)
        self.assertEqual(rows[0]["label"], "protected_exact_control")
        self.assertEqual(rows[0]["status"], "PARENT_BYTES_UNMODIFIED__EVIDENCE_EXTERNAL")

    def test_typed_and_untyped_observational_transports_generated(self):
        rows = self.candidates()
        self.assertEqual(len(rows), 5)
        self.assertEqual(len(set(r["proof_sha256"] for r in rows)), 5)
        self.assertIn("congrArg (fun z => z x) heq", rows[1]["proof"])
        self.assertIn("congrArg (fun z : X → Nat => z x) heq", rows[3]["proof"])
        self.assertIn("exact observed_witness", rows[1]["proof"])
        self.assertTrue(all(r["proof"].startswith(PROOF.split(" := by\n", 1)[0] + " := by\n")
                            for r in rows))
        self.assertTrue(all(r["status"] == "CANDIDATE_UNVERIFIED" for r in rows[1:]))

    def test_suffix_and_original_local_goal_preserved(self):
        for row in self.candidates()[1:]:
            self.assertIn("  have target : f x = g x := by\n", row["proof"])
            self.assertTrue(row["proof"].endswith("  exact target\n"))
            self.assertIn("  have heq : f = g := h\n", row["proof"])

    def test_source_sha_change_requires_new_proof_evidence(self):
        changed = dict(PARENT, proof=PROOF.replace("exact target", "simpa using target"))
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.candidates(parent=changed)

    def test_not_allowed_to_edit_theorem_declaration(self):
        spec = dict(SPEC, exact_site="theorem sampleObservation", goal_prefix="theorem sampleObservation")
        with self.assertRaises(ValueError):
            self.candidates(spec=spec)

    def test_missing_local_equality_refused(self):
        with self.assertRaisesRegex(ValueError, "not introduced"):
            self.candidates(spec=dict(SPEC, equality_name="invented"))

    def test_ambiguous_rewrite_site_refused(self):
        spec = dict(SPEC, exact_site="    ", goal_prefix="    ")
        with self.assertRaisesRegex(ValueError, "uniquely specified"):
            self.candidates(spec=spec)

    def test_bounded_candidate_limit_includes_protected_control(self):
        rows = self.candidates(limit=2)
        self.assertEqual(len(rows), 2)
        with self.assertRaisesRegex(ValueError, "budget"):
            self.candidates(limit=0)

    def test_forbidden_candidate_tactics_rejected(self):
        spec = dict(SPEC, rewrites=[{"id": "attack", "tactics": ["exact sorry"]}])
        with self.assertRaisesRegex(ValueError, "forbidden"):
            self.candidates(spec=spec)

    def test_wrong_theorem_name_refused(self):
        with self.assertRaisesRegex(ValueError, "name or exact"):
            self.candidates(spec=dict(SPEC, name="Other.sampleObservation"))

    def test_repeated_observation_is_deduplicated(self):
        spec = dict(SPEC, observers=[{"id": "one", "term": "(fun z => z x)"},
                                    {"id": "two", "term": "(fun z => z x)"}],
                    rewrites=[{"id": "direct", "tactics": []}])
        self.assertEqual(len(self.candidates(spec=spec)), 2)

    def test_cli_manifest_never_claims_lean_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "parent.jsonl").write_text(json.dumps(PARENT) + "\n")
            (base / "spec.json").write_text(json.dumps(SPEC))
            original_argv = sys.argv
            try:
                sys.argv = [
                    "observation_consequence_compiler.py",
                    "--parent-bank", str(base / "parent.jsonl"),
                    "--parent-label", "control",
                    "--spec", str(base / "spec.json"),
                    "--out", str(base / "out.jsonl"),
                    "--manifest", str(base / "manifest.json"),
                ]
                self.assertEqual(main(), 0)
            finally:
                sys.argv = original_argv
            report = json.loads((base / "manifest.json").read_text())
            self.assertEqual(report["status"], "UNVERIFIED_CANDIDATE_GENERATION_ONLY")
            self.assertFalse(report["officially_submitted"])
            self.assertEqual(report["generated"], 4)


if __name__ == "__main__":
    unittest.main()
