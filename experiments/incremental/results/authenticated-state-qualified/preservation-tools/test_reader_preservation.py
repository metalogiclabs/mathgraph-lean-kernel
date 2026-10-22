"""Small isolated fixtures; never uses the production reader output directory."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('archive_reader_output', HERE / 'archive_reader_output.py')
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


class PreservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='fixture-', dir=HERE)
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.source = self.parent / 'reader-output'
        self.source.mkdir()
        (self.source / 'nested').mkdir()
        (self.source / 'nested/payload').write_bytes(os.urandom(70000))
        (self.source / 'nested/payload').chmod(0o640)
        os.utime(self.source / 'nested/payload', ns=(1700000000123456789, 1700000000123456789))
        os.link(self.source / 'nested/payload', self.source / 'payload-hardlink')
        (self.source / 'empty').write_bytes(b'')
        (self.source / ('long-name-' + 'x' * 130)).write_bytes(b'long tar name\n')
        self.report = dict(schema='mathgraph.authenticated-state-independent-replay.v1',
                           completed=True, passed=True, source_sha=archive.SOURCE_SHA,
                           primary_transition_count=800, fresh_kernel_processes=108)
        self.write_summary()
        self.execution = self.parent / 'execution.json'
        self.execution.write_text(json.dumps(dict(completed=True, returncode=0,
            source_sha=archive.SOURCE_SHA, head_after=archive.SOURCE_SHA,
            run_id=archive.RUN_ID, status_after='', command=['reader.py', '--out', str(self.source)])))
        self.destination = self.parent / 'preserved'

    def write_summary(self):
        (self.source / 'summary.json').write_text(json.dumps(self.report))

    def create(self):
        return archive.archive_source(self.source, self.destination, self.execution, part_bytes=4096)

    def load_verifier(self):
        spec = importlib.util.spec_from_file_location('independent_verifier', HERE / 'verify_reader_archive.py')
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        return verifier

    def complete_proofs(self, manifest_path):
        independent_path = self.destination / 'independent-proof.json'
        self.load_verifier().verify(manifest_path, self.source, independent_path)
        root_proof = self.parent / 'root-proof.json'
        root_proof.write_text(json.dumps(dict(schema='mathgraph.reader-output-root-removal-authorization.v1',
            status='passed', manifest_sha256=archive.file_identity(manifest_path)['sha256'],
            source_root=str(self.source), source_sha=archive.SOURCE_SHA,
            reader_execution_sha256=archive.file_identity(self.execution)['sha256'],
            independent_proof_sha256=archive.file_identity(independent_path)['sha256'])))
        return independent_path, root_proof

    def test_roundtrip_parts_metadata_hardlinks_independent_and_explicit_removal(self):
        before = archive.snapshot(self.source)
        manifest_path = self.create()
        manifest = json.loads(manifest_path.read_bytes())
        self.assertEqual(archive.snapshot(self.source), before)
        self.assertGreater(len(manifest['parts']), 1)
        self.assertTrue(all(part['size'] <= 4096 for part in manifest['parts']))
        independent_path, root_proof = self.complete_proofs(manifest_path)
        self.assertTrue(self.source.exists())
        with mock.patch.object(archive, 'SOURCE', self.source), mock.patch.object(archive, 'EXECUTION', self.execution):
            result = archive.remove_source(manifest_path, independent_path, root_proof)
        self.assertTrue(result['original_tree_removed'])
        self.assertFalse(self.source.exists())
        self.assertTrue(self.execution.exists())
        self.assertTrue(manifest_path.exists())

    def test_incomplete_failed_wrong_source_and_count_refused(self):
        for key, value in [('completed', False), ('passed', False), ('source_sha', 'wrong'),
                           ('primary_transition_count', 799), ('fresh_kernel_processes', 107)]:
            original = self.report[key]
            self.report[key] = value
            self.write_summary()
            with self.assertRaises(ValueError):
                self.create()
            self.assertFalse(self.destination.exists())
            self.assertTrue(self.source.exists())
            self.report[key] = original

    def test_symlink_refused(self):
        (self.source / 'linked').symlink_to(self.execution)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            self.create()
        self.assertFalse(self.destination.exists())

    def test_external_hardlink_refused(self):
        os.link(self.source / 'empty', self.parent / 'outside')
        with self.assertRaisesRegex(ValueError, 'External hardlink'):
            self.create()
        self.assertFalse(self.destination.exists())

    def test_change_during_archive_prevents_pass_and_preserves_source(self):
        original_finish = archive.PartsSink.finish
        source = self.source
        def changed_finish(sink):
            result = original_finish(sink)
            (source / 'new-after-inventory').write_bytes(b'changed')
            return result
        with mock.patch.object(archive.PartsSink, 'finish', changed_finish):
            with self.assertRaisesRegex(ValueError, 'changed while archiving'):
                self.create()
        self.assertTrue(self.source.exists())
        self.assertFalse((self.destination / 'archive-proof.json').exists())

    def test_corrupt_part_refused_by_both_verifiers_and_never_removes_source(self):
        manifest_path = self.create()
        manifest = json.loads(manifest_path.read_bytes())
        part = self.destination / manifest['parts'][1]['name']
        data = bytearray(part.read_bytes())
        data[len(data) // 2] ^= 1
        part.write_bytes(data)
        with self.assertRaises((ValueError, archive.lzma.LZMAError)):
            archive.readback(manifest_path, self.source)
        proof = self.destination / 'independent-proof.json'
        verifier = self.load_verifier()
        with self.assertRaises(Exception):
            verifier.verify(manifest_path, self.source, proof)
        self.assertFalse(proof.exists())
        self.assertTrue(self.source.exists())

    def test_changed_source_fails_independent_verification(self):
        manifest_path = self.create()
        (self.source / 'empty').write_bytes(b'changed')
        proof = self.destination / 'independent-proof.json'
        verifier = self.load_verifier()
        with self.assertRaises(Exception):
            verifier.verify(manifest_path, self.source, proof)
        self.assertFalse(proof.exists())
        self.assertTrue(self.source.exists())

    def test_independent_completion_gate_rejects_incomplete_or_missing_source_summary(self):
        manifest_path = self.create()
        manifest = json.loads(manifest_path.read_bytes())
        verifier = self.load_verifier()
        for key, replacement in [('completed', False), ('source_sha', None)]:
            report = dict(self.report)
            if replacement is None:
                del report[key]
            else:
                report[key] = replacement
            (self.source / 'summary.json').write_text(json.dumps(report))
            identity = archive.file_identity(self.source / 'summary.json')['sha256']
            manifest['completion']['summary_sha256'] = identity
            manifest['entries']['summary.json']['sha256'] = identity
            with self.assertRaisesRegex(Exception, 'completed qualified pass|summary source'):
                verifier._verify_completion(manifest, self.source)

    def test_existing_destination_preserved(self):
        self.destination.mkdir()
        sentinel = self.destination / 'sentinel'
        sentinel.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            self.create()
        self.assertEqual(sentinel.read_bytes(), b'keep')
        self.assertTrue(self.source.exists())

    def test_removal_refuses_arbitrary_source_even_with_bad_proofs(self):
        manifest_path = self.create()
        with self.assertRaisesRegex(ValueError, 'restricted'):
            archive.remove_source(manifest_path, self.parent / 'nonexistent', self.parent / 'nonexistent2')
        self.assertTrue(self.source.exists())

    def test_source_change_after_independent_proof_blocks_removal(self):
        manifest_path = self.create()
        independent, root_proof = self.complete_proofs(manifest_path)
        (self.source / 'empty').write_bytes(b'changed after proof')
        with mock.patch.object(archive, 'SOURCE', self.source), mock.patch.object(archive, 'EXECUTION', self.execution):
            with self.assertRaisesRegex(ValueError, 'Source differs'):
                archive.remove_source(manifest_path, independent, root_proof)
        self.assertTrue(self.source.exists())
        self.assertFalse((self.destination / 'removal-proof.json').exists())

    def test_corruption_after_independent_proof_blocks_removal(self):
        manifest_path = self.create()
        independent, root_proof = self.complete_proofs(manifest_path)
        manifest = json.loads(manifest_path.read_bytes())
        part = self.destination / manifest['parts'][1]['name']
        part.write_bytes(part.read_bytes()[:-1])
        with mock.patch.object(archive, 'SOURCE', self.source), mock.patch.object(archive, 'EXECUTION', self.execution):
            with self.assertRaises(Exception):
                archive.remove_source(manifest_path, independent, root_proof)
        self.assertTrue(self.source.exists())
        self.assertFalse((self.destination / 'removal-proof.json').exists())

    def test_failed_root_proof_blocks_removal(self):
        manifest_path = self.create()
        independent, root_proof = self.complete_proofs(manifest_path)
        root_value = json.loads(root_proof.read_bytes())
        root_value['status'] = 'failed'
        root_proof.write_text(json.dumps(root_value))
        with mock.patch.object(archive, 'SOURCE', self.source), mock.patch.object(archive, 'EXECUTION', self.execution):
            with self.assertRaisesRegex(ValueError, 'Root removal proof'):
                archive.remove_source(manifest_path, independent, root_proof)
        self.assertTrue(self.source.exists())
        self.assertFalse((self.destination / 'removal-proof.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
