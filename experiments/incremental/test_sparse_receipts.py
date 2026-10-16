"""Storage decoder tests only; these HMAC fixtures are not kernel evidence."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path


class SparseStorageTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(Path(__file__).with_name('benchmark_sparse_receipts.py').exists(),
                        'sparse storage experiment has not been implemented')
        import benchmark_sparse_receipts as b
        self.b = b
        self.key = bytes(range(32))
        declaration = dict(index=0, key='a', own='old', closure='old', deps=[], name='a', kind='def')
        index = dict(meta={}, count=1, builtins={}, complex='x', schedule='s', declarations=[declaration])
        self.base = dict(schema=b.engine.SCHEMA, status='VERIFIED', index=index,
                         provenance={'policy': 'fixture'}, export_sha256='base')
        self.base_raw, self.base_id = b.mint_original(self.base, self.key)
        self.current = copy.deepcopy(self.base)
        self.current.update(previous_evidence=self.base_id, export_sha256='current')
        self.current['index']['declarations'][0].update(own='new', closure='new')
        self.raw, self.original_id = b.mint_original(self.current, self.key)
        self.cap = b.representation(self.base, self.base_id, self.current,
                                    b.decode(self.raw)['hmac_sha256'], self.original_id)

    def read(self, cap=None, base_raw=None, key=None):
        cap = self.cap if cap is None else cap
        raw = self.b.engine.encoded(self.b.seal(cap, self.key))
        return self.b.expand(raw, self.b.sha(raw),
                             lambda ident: self.base_raw if base_raw is None else base_raw,
                             self.key if key is None else key)

    def test_roundtrip_returns_exact_original_authenticated_record(self):
        self.assertEqual(self.read(), self.current)

    def test_validly_signed_wrong_patch_cannot_reuse_original_acceptance(self):
        cap = copy.deepcopy(self.cap)
        cap['replacements'][0]['declaration']['own'] = 'forged'
        with self.assertRaisesRegex(ValueError, 'evidence content address mismatch'):
            self.read(cap)

    def test_updated_content_address_cannot_bypass_original_hmac(self):
        cap = copy.deepcopy(self.cap)
        cap['replacements'][0]['declaration']['own'] = 'forged'
        changed = copy.deepcopy(self.current)
        changed['index']['declarations'][0]['own'] = 'forged'
        envelope = self.b.engine.encoded(dict(payload=changed,
            hmac_sha256=cap['accepted_hmac_sha256']))
        cap['accepted_evidence_id'] = self.b.sha(envelope)
        with self.assertRaisesRegex(ValueError, 'evidence issuer authentication failed'):
            self.read(cap)

    def test_completed_fail_status_cannot_open_parity_gate(self):
        report = dict(schema='mathgraph.retained-index-qualification.v1',
                      run_completed=True, correctness_passed=True,
                      qualification_status='FAIL', gates=[{'passed': True}])
        with self.assertRaisesRegex(ValueError, 'parity gate'):
            self.b.validate_parity_gate(report, False)

    def test_corrupt_baseline_refuses(self):
        with self.assertRaisesRegex(ValueError, 'evidence content address mismatch'):
            self.read(base_raw=self.base_raw + b' ')

    def test_duplicate_patch_refuses(self):
        cap = copy.deepcopy(self.cap)
        cap['replacements'] *= 2
        with self.assertRaisesRegex(ValueError, 'patch positions'):
            self.read(cap)

    def test_boolean_patch_position_refuses(self):
        cap = copy.deepcopy(self.cap)
        cap['replacements'][0]['position'] = False
        with self.assertRaisesRegex(ValueError, 'patch positions'):
            self.read(cap)

    def test_signed_version_drift_refuses(self):
        cap = copy.deepcopy(self.cap)
        cap['schema'] += '.wrong'
        with self.assertRaisesRegex(ValueError, 'wrong authority domain'):
            self.read(cap)

    def test_wrong_key_refuses(self):
        with self.assertRaisesRegex(ValueError, 'issuer authentication failed'):
            self.read(key=b'x' * 32)

    def test_baseline_guard_refuses_validly_signed_patch(self):
        cap = copy.deepcopy(self.cap)
        cap['replacements'][0]['baseline_own'] = 'foreign'
        with self.assertRaisesRegex(ValueError, 'baseline patch guard'):
            self.read(cap)

    def test_foreign_previous_evidence_refuses_before_representation(self):
        self.current['previous_evidence'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'previous baseline'):
            self.b.representation(self.base, self.base_id, self.current, 'sig', 'id')

    def test_duplicate_json_fields_refuse(self):
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            self.b.decode(b'{"payload":1,"payload":2}')


if __name__ == '__main__':
    unittest.main()
