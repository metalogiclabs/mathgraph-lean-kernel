"""Adversarial artifact access checks; standard library and no extraction."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
import zipfile

from artifacts import Artifacts


class ArtifactAdversarialTests(unittest.TestCase):
    def fixture(self, root, prefix='revision-chain', original='/old/revision-chain'):
        raw = b'actual input'
        blob = gzip.compress(raw, mtime=0)
        record = dict(path=original + '/witnesses/input.gz',
                      artifact_relative_path='witnesses/input.gz', encoding='gzip',
                      sha256=hashlib.sha256(blob).hexdigest(), bytes=len(blob),
                      uncompressed_sha256=hashlib.sha256(raw).hexdigest(),
                      uncompressed_bytes=len(raw))
        folder = root / prefix
        (folder / 'witnesses').mkdir(parents=True)
        (folder / 'witnesses/input.gz').write_bytes(blob)
        report = dict(schema='mathgraph.authenticated-revision-chain-lifecycle.v1',
                      profiles={'original': dict(pairs=[dict(genesis=dict(baseline_witness=record))])})
        (folder / 'summary.json').write_text(json.dumps(report))
        return record, folder / 'witnesses/input.gz'

    def zipped(self, root, archive):
        with zipfile.ZipFile(archive, 'w') as output:
            for path in root.rglob('*'):
                if path.is_file():
                    output.write(path, str(path.relative_to(root)))

    def test_duplicate_zip_members_and_canonical_aliases_are_rejected(self):
        for alias in ('revision-chain/witnesses/input.gz',
                      'revision-chain/witnesses/./input.gz',
                      'revision-chain//witnesses/input.gz'):
            with self.subTest(alias=alias), tempfile.TemporaryDirectory() as td:
                root = Path(td) / 'data'; root.mkdir()
                self.fixture(root)
                archive = Path(td) / 'evidence.zip'
                self.zipped(root, archive)
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)
                    with zipfile.ZipFile(archive, 'a') as output:
                        output.writestr(alias, b'contradictory duplicate')
                with self.assertRaisesRegex(ValueError, 'duplicate ZIP member'):
                    Artifacts(archive)

    def test_zip_symlink_and_member_traversal_are_rejected(self):
        for member in ('../outside', '/absolute', 'revision-chain/../../outside', 'bad\\path'):
            with self.subTest(member=member), tempfile.TemporaryDirectory() as td:
                archive = Path(td) / 'bad.zip'
                with zipfile.ZipFile(archive, 'w') as output:
                    output.writestr(member, b'bad')
                with self.assertRaises(ValueError):
                    Artifacts(archive)
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / 'symlink.zip'
            entry = zipfile.ZipInfo('revision-chain/link')
            entry.create_system = 3
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(archive, 'w') as output:
                output.writestr(entry, b'../../outside')
            with self.assertRaisesRegex(ValueError, 'symlink'):
                Artifacts(archive)

    def test_directory_symlink_escape_and_missing_object_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'data'; root.mkdir()
            record, blob = self.fixture(root)
            outside = Path(td) / 'outside.gz'
            outside.write_bytes(blob.read_bytes())
            blob.unlink(); blob.symlink_to(outside)
            store = Artifacts(root)
            with self.assertRaisesRegex(ValueError, 'symlink escapes'):
                store.archive(record)
            with self.assertRaisesRegex(ValueError, 'missing artifact object'):
                store.saved('/old/revision-chain/missing.json')

    def test_ci_recorded_paths_map_under_both_zip_layouts(self):
        original = '/home/runner/work/project/project/artifacts/revision-chain'
        for prefix in ('revision-chain', 'artifacts/revision-chain'):
            with self.subTest(prefix=prefix), tempfile.TemporaryDirectory() as td:
                root = Path(td) / 'data'; root.mkdir()
                record, _ = self.fixture(root, prefix, original)
                archive = Path(td) / 'evidence.zip'
                self.zipped(root, archive)
                store = Artifacts(archive)
                expected = prefix + '/witnesses/input.gz'
                for recorded in (original + '/witnesses/input.gz',
                                 'artifacts/revision-chain/witnesses/input.gz'):
                    self.assertEqual(store.map(recorded), expected)
                self.assertEqual(store.archive(record), expected)
                for recorded in (original + '/../outside', '/outside/secret'):
                    with self.assertRaises(ValueError):
                        store.map(recorded)

    def test_descriptors_refuse_type_aliases_corruption_and_cache_conflicts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            record, _ = self.fixture(root)
            store = Artifacts(root)
            store.archive(record)
            mutations = [dict(record, bytes=True), dict(record, uncompressed_bytes=-1),
                         dict(record, sha256='F' * 64), dict(record, encoding='base64'),
                         dict(record, artifact_relative_path='../outside'),
                         dict(record, uncompressed_sha256='0' * 64)]
            for changed in mutations:
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    store.archive(changed)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            record, blob = self.fixture(root)
            compressed = blob.read_bytes()[:-5]
            blob.write_bytes(compressed)
            record.update(sha256=hashlib.sha256(compressed).hexdigest(), bytes=len(compressed))
            with self.assertRaises((ValueError, OSError, EOFError)):
                Artifacts(root).archive(record)

    def test_cached_directory_blob_cannot_disappear_silently(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            record, blob = self.fixture(root)
            store = Artifacts(root)
            store.archive(record)
            blob.unlink()
            with self.assertRaises((ValueError, OSError)):
                store.archive(record)

    def test_cached_directory_blob_cannot_change_silently(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            record, blob = self.fixture(root)
            store = Artifacts(root)
            store.archive(record)
            blob.write_bytes(b'corruption after first validation')
            with self.assertRaises((ValueError, OSError)):
                store.archive(record)


if __name__ == '__main__':
    unittest.main(verbosity=2)
