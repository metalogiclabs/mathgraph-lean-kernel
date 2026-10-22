import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from artifacts import Artifacts, loads


class ArtifactTests(unittest.TestCase):
    def fixture(self, root):
        blob = gzip.compress(b'actual input', mtime=0)
        record = dict(path='/old/revision-chain/witnesses/input.gz', artifact_relative_path='witnesses/input.gz',
                      sha256=hashlib.sha256(blob).hexdigest(), bytes=len(blob), encoding='gzip',
                      uncompressed_sha256=hashlib.sha256(b'actual input').hexdigest(), uncompressed_bytes=12)
        target = root/'revision-chain/witnesses/input.gz'
        target.parent.mkdir(parents=True)
        target.write_bytes(blob)
        report = dict(schema='mathgraph.authenticated-revision-chain-lifecycle.v1', profiles={
            'original':dict(pairs=[dict(genesis=dict(baseline_witness=record))])})
        (root/'revision-chain/summary.json').write_text(json.dumps(report))
        return record

    def test_missing_and_contradictory_cached_descriptor_refuse(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);record=self.fixture(root);store=Artifacts(root)
            store.archive(record)
            false=dict(record,uncompressed_sha256='0'*64)
            with self.assertRaisesRegex(ValueError,'contradictory'):
                store.archive(false)
            (root/'revision-chain/witnesses/input.gz').unlink()
            with self.assertRaisesRegex(ValueError,'missing'):
                Artifacts(root).archive(record)

    def test_zip_maps_historical_paths_without_extraction(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'data';root.mkdir();record=self.fixture(root)
            archive=Path(td)/'artifact.zip'
            with zipfile.ZipFile(archive,'w') as z:
                for p in root.rglob('*'):
                    if p.is_file():z.write(p,str(p.relative_to(root)))
            store=Artifacts(archive)
            self.assertEqual(store.map('/old/revision-chain/witnesses/input.gz'),'revision-chain/witnesses/input.gz')
            self.assertEqual(store.archive(record),'revision-chain/witnesses/input.gz')

    def test_duplicate_json_and_zip_traversal_refuse(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):
            loads(b'{"head":1,"head":2}')
        with tempfile.TemporaryDirectory() as td:
            archive=Path(td)/'bad.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('../secret',b'bad')
            with self.assertRaisesRegex(ValueError,'traversal'):
                Artifacts(archive)


if __name__=='__main__':unittest.main()
