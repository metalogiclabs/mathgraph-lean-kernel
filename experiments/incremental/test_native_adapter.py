#!/usr/bin/env python3
"""Adversarial identity-adapter tests using the real selected kernel checker.

The tiny, well-typed exported declarations isolate the protocol and authority
boundary. Identity helpers below are deliberately adversarial test executables;
none replaces the kernel checker or supplies acceptance evidence. Real pinned
Lean exports and independent full oracles are exercised by qualify_native.py.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import engine

ROOT = Path(__file__).resolve().parents[2]
CHECKER = Path(os.environ.get('MATHGRAPH_SELECTED_CHECKER', ROOT / 'target/release/check-selected'))


def export_bytes():
    # sample : Type := Prop. Its value has exactly the declared type.
    rows = [
        {'meta': {'lean': {'version': '4.35.0', 'githash': 'adapter-boundary-test'},
                  'exporter': {'name': 'lean4export', 'version': '3.1.0'},
                  'format': {'version': '3.1.0'}, 'typed_probe': True}},
        {'il': 1, 'succ': 0},
        {'ie': 0, 'sort': 0},
        {'ie': 1, 'sort': 1},
        {'in': 1, 'str': {'pre': 0, 'str': 'sample'}},
        {'def': {'name': 1, 'levelParams': [], 'type': 1, 'value': 0,
                 'hints': 'abbrev', 'safety': 'safe', 'all': []}},
    ]
    return b''.join(engine.encoded(row) + b'\n' for row in rows)


class NativeAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checker = CHECKER.expanduser().resolve()
        if not cls.checker.is_file() or not os.access(cls.checker, os.X_OK):
            raise RuntimeError(f'actual selected checker missing: {cls.checker}; '
                               'build cargo build --release --bin check-selected')

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-adapter-test-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.export = self.directory / 'export.ndjson'
        self.export.write_bytes(export_bytes())
        self.index = engine.make_index(self.export)
        self.cache = self.directory / 'evidence'
        # Issuer authority is deliberately outside the evidence/cache directory.
        self.key = self.directory / 'authority' / 'issuer.key'
        self.key.parent.mkdir()
        self.key.write_bytes(os.urandom(32))
        self.key.chmod(0o600)
        self.helper_number = 0

    def helper(self, value=None, *, raw=None, code=0, tail='', comment=''):
        """An identity-protocol falsifier, never a kernel-checker replacement."""
        self.helper_number += 1
        path = self.directory / f'identity-protocol-{self.helper_number}'
        data = engine.encoded(self.index if value is None else value) if raw is None else raw
        source = ('#!/usr/bin/env python3\n'
                  'import os, resource, signal, sys\n'
                  'resource.setrlimit(resource.RLIMIT_CORE, (0, 0))\n'
                  f'sys.stdout.buffer.write({data!r})\n'
                  'sys.stdout.buffer.flush()\n' + tail + '\n' +
                  f'sys.exit({code})\n# {comment}\n')
        path.write_text(source)
        path.chmod(0o700)
        return path

    def policy(self, indexer, backend='native'):
        return dict(checker=self.checker, cache=self.cache, authority_key=self.key,
                    indexer=indexer, identity_backend=backend, timeout=10)

    def verify(self, indexer, *, previous=None, backend='native', export=None):
        return engine.verify_incremental(previous, export or self.export,
                                         self.policy(indexer, backend))

    def assert_no_receipt(self):
        self.assertFalse(self.cache.exists() and any(self.cache.rglob('*.json')),
                         'a declined identity protocol must not mint acceptance evidence')

    def test_differential_mismatch_never_mints_evidence(self):
        wrong = copy.deepcopy(self.index)
        wrong['declarations'][0]['closure'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'identity disagreement'):
            self.verify(self.helper(wrong), backend='differential')
        self.assert_no_receipt()

    def test_differential_compares_json_types_not_python_equality(self):
        wrong = copy.deepcopy(self.index)
        wrong['meta']['typed_probe'] = 1
        self.assertEqual(self.index, wrong, 'fixture must expose Python bool/int equality')
        with self.assertRaisesRegex(ValueError, 'identity disagreement'):
            self.verify(self.helper(wrong), backend='differential')
        self.assert_no_receipt()

    def test_duplicate_json_keys_are_not_native_evidence(self):
        raw = b'{"meta":null,"meta":null}'
        with self.assertRaisesRegex(ValueError, 'invalid native identity protocol'):
            self.verify(self.helper(raw=raw))
        self.assert_no_receipt()

    def test_unstructured_failure_and_truncated_success_fail_closed(self):
        for raw, code in ((b'not JSON', 1), (b'{"meta":{}}', 0)):
            with self.subTest(raw=raw, code=code):
                with self.assertRaises(ValueError):
                    self.verify(self.helper(raw=raw, code=code))
                self.assert_no_receipt()

    def test_signal_after_refusal_is_a_crash_not_a_decline(self):
        refusal = dict(status='error', stage='identity', error='unsupported test field', declined=True)
        indexer = self.helper(refusal, tail='os.kill(os.getpid(), signal.SIGABRT)')
        with self.assertRaisesRegex(ValueError, 'unexplained native identity failure'):
            self.verify(indexer)
        self.assert_no_receipt()

    def test_native_timeout_authorizes_no_evidence(self):
        indexer = self.helper(tail='import time; time.sleep(5)')
        policy = self.policy(indexer)
        policy['timeout'] = 0.05
        with self.assertRaisesRegex(ValueError, 'native identity timeout'):
            engine.verify_incremental(None, self.export, policy)
        self.assert_no_receipt()

    def test_wrong_refusal_exit_code_and_extra_fields_fail_closed(self):
        refusal = dict(status='error', stage='identity', error='unsupported test field', declined=True)
        cases = [(refusal, 1), (refusal, 3), (dict(refusal, extra='unrecognized'), 2),
                 (dict(refusal, declined='true'), 2)]
        for value, code in cases:
            with self.subTest(value=value, code=code):
                with self.assertRaisesRegex(ValueError, 'unexplained native identity failure'):
                    self.verify(self.helper(value, code=code))
                self.assert_no_receipt()

    def test_explicit_decline_falls_back_to_real_kernel_check(self):
        refusal = dict(status='error', stage='identity', error='explicit unsupported test field', declined=True)
        result = self.verify(self.helper(refusal, code=2))
        self.assertEqual(result['status'], 'VERIFIED')
        self.assertEqual(result['counts']['rechecked'], 1)
        self.assertEqual(result['identity_backend']['used'], 'python_fallback')
        self.assertEqual(json.loads(result['checker_result']['stdout'])['checked'], 1)
        self.assertIsNotNone(result['evidence_id'])

    def test_kernel_parse_refusal_does_not_bypass_actual_parser(self):
        refusal = dict(status='error', stage='kernel_parse', error='deliberate parser rejection', declined=False)
        # The Python identity accepts this unused ill-typed serialized node;
        # the actual selected kernel parser must still reject its changed bytes.
        self.export.write_bytes(export_bytes() + b'{"bvar":"not-an-integer","ie":2}\n')
        self.assertEqual(self.index, engine.make_index(self.export))
        result = self.verify(self.helper(refusal, code=1))
        self.assertEqual(result['status'], 'REJECTED')
        self.assertIsNone(result['evidence_id'])
        self.assertEqual(result['identity_backend']['used'], 'python_fallback')
        self.assert_no_receipt()

    def test_zero_selected_changed_valid_bytes_are_actually_parsed(self):
        indexer = self.helper()
        seed = self.verify(indexer)
        self.assertEqual(seed['status'], 'VERIFIED')
        changed = self.directory / 'reserialized.ndjson'
        changed.write_bytes(export_bytes().replace(b'"meta":', b'"meta" : '))
        result = self.verify(indexer, previous=seed['evidence_id'], export=changed)
        self.assertEqual(result['status'], 'VERIFIED')
        self.assertEqual(result['counts']['scheduled'], 0)
        self.assertEqual(result['counts']['reused'], 1)
        report = json.loads(result['checker_result']['stdout'])
        self.assertEqual(report['checked'], 0)
        self.assertEqual(report['total_declarations'], 1)

    def test_zero_selected_changed_invalid_unused_node_is_rejected(self):
        indexer = self.helper()
        seed = self.verify(indexer)
        changed = self.directory / 'invalid-unused-node.ndjson'
        changed.write_bytes(export_bytes() + b'{"bvar":"not-an-integer","ie":2}\n')
        result = self.verify(indexer, previous=seed['evidence_id'], export=changed)
        self.assertEqual(result['counts']['scheduled'], 0)
        self.assertEqual(result['status'], 'REJECTED')
        self.assertIsNone(result['evidence_id'])
        self.assertEqual(len(list((self.cache / 'records').glob('*.json'))), 1,
                         'only the original checked environment may retain a receipt')

    def test_changed_indexer_bytes_revoke_previous_reuse(self):
        first, second = self.helper(comment='first implementation'), self.helper(comment='second implementation')
        seed = self.verify(first)
        self.assertEqual(seed['status'], 'VERIFIED')
        result = self.verify(second, previous=seed['evidence_id'])
        self.assertEqual(result['status'], 'VERIFIED')
        self.assertNotEqual(seed['provenance']['indexer_sha256'], result['provenance']['indexer_sha256'])
        self.assertEqual(result['counts']['reused'], 0)
        self.assertEqual(result['counts']['rechecked'], 1)
        self.assertEqual(result['decisions'][0]['reason'], 'toolchain_or_policy_changed')

    def test_exact_authenticated_export_reuses_without_running_indexer(self):
        calls = self.directory / 'identity-invocations'
        indexer = self.helper(tail=f'open({str(calls)!r}, "ab").write(b"called\\n")')
        seed = self.verify(indexer)
        self.assertEqual(calls.read_bytes(), b'called\n')
        result = self.verify(indexer, previous=seed['evidence_id'])
        self.assertEqual(result['status'], 'VERIFIED')
        self.assertEqual(result['counts']['rechecked'], 0)
        self.assertEqual(result['identity_backend']['used'], 'authenticated_exact_export')
        self.assertEqual(calls.read_bytes(), b'called\n')

    def test_indexer_source_mutation_cannot_change_captured_executable(self):
        indexer = self.helper()
        captured_sha = hashlib.sha256(indexer.read_bytes()).hexdigest()
        original = engine._verify_with_binary

        def mutate_after_capture(*args, **kwargs):
            indexer.write_text('#!/usr/bin/env python3\nraise SystemExit(99)\n')
            return original(*args, **kwargs)

        with patch.object(engine, '_verify_with_binary', side_effect=mutate_after_capture):
            result = self.verify(indexer)
        self.assertEqual(result['status'], 'VERIFIED')
        self.assertEqual(result['provenance']['indexer_sha256'], captured_sha)
        self.assertNotEqual(captured_sha, hashlib.sha256(indexer.read_bytes()).hexdigest())

    def test_cli_protocol_failure_is_unknown_and_persists_no_receipt(self):
        indexer = self.helper(raw=b'crashed before returning a witness', code=1)
        output = self.directory / 'result.json'
        command = [sys.executable, str(Path(engine.__file__).resolve()),
                   '--export', str(self.export), '--checker', str(self.checker),
                   '--cache', str(self.cache), '--authority-key', str(self.key),
                   '--output', str(output), '--identity-backend', 'native', '--indexer', str(indexer)]
        run = subprocess.run(command, capture_output=True, timeout=20)
        self.assertEqual(run.returncode, 2)
        result = json.loads(output.read_bytes())
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertIsNone(result['evidence_id'])
        self.assert_no_receipt()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checker', type=Path)
    options, remaining = parser.parse_known_args()
    if options.checker:
        CHECKER = options.checker
    unittest.main(argv=[sys.argv[0]] + remaining)
