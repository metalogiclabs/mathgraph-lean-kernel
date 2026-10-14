import copy
import json
import pathlib
import unittest

from reconcile_v16 import qualify

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/reconcile_v16_20261015'


class ReconcileTests(unittest.TestCase):
    def fiber(self):
        proof = json.loads((EVIDENCE / 'fiber_proof.json').read_text())
        source = json.loads((EVIDENCE / 'fiber_source.json').read_text())
        score = json.loads((EVIDENCE / 'fiber_winner.json').read_text())
        return proof, source, score

    def test_source_bound_four_version_winner(self):
        proof, source, score = self.fiber()
        qualify(proof, source['winner_sha256'], score, source['required_versions'])

    def test_changed_proof_rejected(self):
        proof, source, score = self.fiber()
        proof['proof'] += '\n  sorry'
        with self.assertRaises(ValueError):
            qualify(proof, source['winner_sha256'], score, source['required_versions'])

    def test_missing_version_rejected(self):
        proof, source, score = self.fiber()
        score['per_version'].pop()
        with self.assertRaises(ValueError):
            qualify(proof, source['winner_sha256'], score, source['required_versions'])

    def test_failed_version_rejected_even_with_positive_summary(self):
        proof, source, score = self.fiber()
        score['per_version'][0]['ok'] = False
        with self.assertRaises(ValueError):
            qualify(proof, source['winner_sha256'], score, source['required_versions'])

    def test_current_packet_matches_v16_audit(self):
        audit = json.loads((ROOT / 'evidence/retained_exact_full_version_audit_20261015_v16.json').read_text())
        rows = [json.loads(s) for s in (ROOT / 'portfolio/warmup_portfolio_v1.jsonl').read_text().splitlines()]
        packet = [json.loads(s) for s in (ROOT / 'submissions/mathgraph_verified_15_warmup_20261009.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows), 15)
        self.assertEqual([(r['name'], r['proof']) for r in rows], [(r['name'], r['proof']) for r in packet])
        self.assertEqual(audit['change_fingerprint']['preserved_proof_rows_from_v15'], 13)
        self.assertEqual(audit['protected_future_invariant'], 'Thirteen V15 rows byte-identical; six external and nine independent exact required-version authorities; no new Lean replay.')
        self.assertAlmostEqual(audit['projected_score']['combined_pct_if_full_survival'], 82.9584, places=4)
