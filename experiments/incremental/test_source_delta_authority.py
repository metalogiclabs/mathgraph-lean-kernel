#!/usr/bin/env python3
"""Independent small authority/materialization controls; real parser, no Lean mocks."""
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import engine
import producer_delta as delta
from test_native_adapter import export_bytes

ROOT = Path(__file__).resolve().parents[2]
CHECKER = Path(os.environ.get('MATHGRAPH_SELECTED_CHECKER', ROOT / 'target/release/check-selected'))


class SourceDeltaAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.key = bytes(range(32))
        self.temp = tempfile.TemporaryDirectory(prefix='independent-source-delta-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def test_each_hmac_purpose_refuses_the_other_domains(self):
        for schema in [delta.GENESIS, delta.TRANSITION, engine.SCHEMA]:
            signed = delta.seal(dict(schema=schema, status='VERIFIED'), self.key)
            self.assertEqual(delta.authenticate(signed, self.key, schema), signed['payload'])
            for other in [delta.GENESIS, delta.TRANSITION, engine.SCHEMA]:
                if other != schema:
                    with self.subTest(schema=schema, other=other), self.assertRaisesRegex(ValueError, 'domain'):
                        delta.authenticate(signed, self.key, other)
            if schema != engine.SCHEMA:
                raw = engine.encoded(signed)
                with self.assertRaisesRegex(ValueError, 'not accepted'):
                    engine.authenticate_record(raw, hashlib.sha256(raw).hexdigest(), self.key)

    def test_changed_payload_foreign_key_and_extra_envelope_field_are_refused(self):
        signed = delta.seal(dict(schema=delta.TRANSITION, delta_sha256='original'), self.key)
        altered = copy.deepcopy(signed)
        altered['payload']['delta_sha256'] = 'forged'
        for envelope, key in [(altered, self.key), (signed, b'x' * 32),
                              (dict(signed, ignored='field'), self.key)]:
            with self.assertRaises(ValueError):
                delta.authenticate(envelope, key, delta.TRANSITION)

    def write_sources(self):
        for name in delta.SOURCES:
            path = self.directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('pinned source\n')
        return delta.sources_at(self.directory)

    def test_complete_six_file_capture_refuses_extra_lean_and_missing_config(self):
        captured = self.write_sources()
        self.assertEqual(set(captured), set(delta.SOURCES))
        extra = self.directory / 'Extra.lean'
        extra.write_text('-- outside the owned universe\n')
        with self.assertRaisesRegex(ValueError, 'universe'):
            delta.sources_at(self.directory)
        extra.unlink()
        (self.directory / 'lakefile.toml').unlink()
        with self.assertRaises(OSError):
            delta.sources_at(self.directory)

    def test_source_symlink_is_refused(self):
        self.write_sources()
        path = self.directory / 'Workload.lean'
        target = self.directory / 'actual-source.txt'
        path.rename(target)
        path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            delta.sources_at(self.directory)

    def test_outside_announced_patch_is_refused_before_producer(self):
        baseline = self.write_sources()
        session = object.__new__(delta.DeltaSession)
        session.baseline_sources = baseline
        session.producer = None
        session.index = None
        (self.directory / 'Workload.lean').write_text('outside edit\n')
        with self.assertRaisesRegex(ValueError, 'outside the reported patch'):
            session.prepare(self.directory, ('IncrementalWorkload/Base.lean',
                                            'pinned source', 'changed source'), [])

    def assert_configuration_patch_refused(self, filename):
        class ProducerMustNotRun:
            def request(self, request):
                raise AssertionError('configuration drift reached the producer')
        baseline = self.write_sources()
        session = object.__new__(delta.DeltaSession)
        session.baseline_sources = baseline
        session.producer = ProducerMustNotRun()
        session.cpu_time = lambda: 0
        session.index = None
        session.temp = self.directory
        (self.directory / filename).write_text('changed configuration\n')
        with self.assertRaisesRegex(ValueError, 'configuration|editable|fixed|unsupported'):
            session.prepare(self.directory, (filename, 'pinned source', 'changed configuration'), [])

    def test_explicit_lean_toolchain_patch_is_refused_before_producer(self):
        self.assert_configuration_patch_refused('lean-toolchain')

    def test_explicit_lakefile_patch_is_refused_before_producer(self):
        self.assert_configuration_patch_refused('lakefile.toml')

    def materialize(self, changed=b'', names=()):
        baseline = export_bytes()
        session = object.__new__(delta.DeltaSession)
        session.layout = session._layout(baseline)
        session.fd = None
        try:
            export_hash, size = session._materialize(baseline, changed, names)
        except Exception:
            if session.fd is not None:
                os.close(session.fd)
            raise
        self.addCleanup(os.close, session.fd)
        actual = Path(session.snapshot_path).read_bytes()
        self.assertEqual(export_hash, hashlib.sha256(actual).hexdigest())
        self.assertEqual(size, len(actual))
        return session, actual

    def test_materialized_input_is_fully_sealed_against_write_resize_and_seal_removal(self):
        session, _ = self.materialize()
        seals = fcntl.fcntl(session.fd, getattr(fcntl, 'F_GET_SEALS', 1034))
        self.assertEqual(seals & 15, 15)
        for operation in [lambda: os.write(session.fd, b'forged'),
                          lambda: os.ftruncate(session.fd, 0),
                          lambda: os.ftruncate(session.fd, 10_000_000),
                          lambda: fcntl.fcntl(session.fd, getattr(fcntl, 'F_ADD_SEALS', 1033), 0)]:
            with self.assertRaises(OSError):
                operation()

    def test_materialization_preserves_complete_index_for_unchanged_input(self):
        _, composite = self.materialize()
        before = self.directory / 'baseline.ndjson'
        after = self.directory / 'composite.ndjson'
        before.write_bytes(export_bytes())
        after.write_bytes(composite)
        self.assertEqual(engine.encoded(engine.make_index(before)),
                         engine.encoded(engine.make_index(after)))

    def test_parser_rejects_changed_unused_malformed_node_with_zero_selected(self):
        checker = CHECKER.resolve()
        self.assertTrue(checker.is_file(), f'real checker missing: {checker}')
        session, _ = self.materialize(engine.encoded({'ie': 2, 'bvar': 'ill-typed'}) + b'\n')
        config, selected = self.directory / 'config.json', self.directory / 'indices.json'
        config.write_bytes(engine.encoded(dict(export_file_path=session.snapshot_path,
            nat_extension=True, string_extension=True,
            permitted_axioms=engine.STANDARD_AXIOMS, num_threads=1,
            unpermitted_axiom_hard_error=True)))
        selected.write_bytes(b'[]')
        run = subprocess.run([str(checker), str(config), str(selected)], capture_output=True, timeout=10)
        self.assertNotEqual(run.returncode, 0, 'unused changed rows must still pass the genuine parser')

    def test_materialization_refuses_declaration_addition_and_metadata(self):
        for row in [{'meta': {}}, {'inductive': {'types': [], 'ctors': [], 'recs': []}}]:
            with self.assertRaisesRegex(ValueError, 'global/schedule'):
                self.materialize(engine.encoded(row) + b'\n')
        definition = json.loads(export_bytes().splitlines()[-1])
        definition['def']['name'] = 2
        addition = b''.join(engine.encoded(row) + b'\n' for row in [
            {'in': 2, 'str': {'pre': 0, 'str': 'new'}}, definition])
        with self.assertRaisesRegex(ValueError, 'new declaration or schedule'):
            self.materialize(addition, ['new'])


if __name__ == '__main__':
    unittest.main()
