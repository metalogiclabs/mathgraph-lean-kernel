"""Bound large lifecycle JSON by its explicit role; keep generic reads small."""
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from artifacts import Artifacts

MIB=1024*1024


def write_fixture(root,padding):
    folder=root/'revision-chain';folder.mkdir(parents=True)
    report=dict(schema='mathgraph.authenticated-revision-chain-lifecycle.v1',profiles={
        'original':dict(pairs=[dict(genesis=dict(baseline_witness=dict(
            path='/old/revision-chain/witnesses/input.gz',artifact_relative_path='witnesses/input.gz')))])})
    prefix=json.dumps(report)[:-1].encode()+b',"fixture_padding":"'
    path=folder/'summary.json'
    h=hashlib.sha256()
    with path.open('wb') as stream:
        for data in (prefix,b'x'*padding,b'"}'):
            stream.write(data);h.update(data)
    return path,h.hexdigest()


class LargeLifecycleSummaryTests(unittest.TestCase):
    def accepted(self,path):
        try:return Artifacts(path)
        except ValueError as error:self.fail('valid role-restricted >64MiB lifecycle summary was refused: '+str(error))

    def test_valid_lifecycle_over64mib_is_read_by_explicit_role(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);path,identity=write_fixture(root,64*MIB+1024)
            self.assertGreater(path.stat().st_size,64*MIB)
            evidence=Path(__file__).with_name('size-cap-evidence');evidence.mkdir(exist_ok=True)
            compressed=evidence/'large-lifecycle-summary.json.gz'
            with path.open('rb') as src,gzip.open(compressed,'wb') as dst:
                for chunk in iter(lambda:src.read(1<<20),b''):dst.write(chunk)
            (evidence/'large-lifecycle-summary.json.meta').write_text(json.dumps(dict(
                valid_json=True,uncompressed_bytes=path.stat().st_size,uncompressed_sha256=identity,
                padding_bytes=64*MIB+1024,compressed_sha256=hashlib.sha256(compressed.read_bytes()).hexdigest()),indent=2)+'\n')
            store=self.accepted(root)
            result=store.json(store.summary_member)
            self.assertEqual(len(result['fixture_padding']),64*MIB+1024)
            self.assertEqual(store.stream_hash(store.summary_member)[0],identity)

    def test_compact_zip_large_lifecycle_summary_uses_scoped_limit(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'data';root.mkdir();path,_=write_fixture(root,64*MIB+1024)
            archive=Path(td)/'artifact.zip'
            with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
                z.write(path,'revision-chain/summary.json')
            store=self.accepted(archive)
            self.assertEqual(len(store.json(store.summary_member)['fixture_padding']),64*MIB+1024)

    def test_generic_logs_keep_default64mib_bound(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);write_fixture(root,0)
            path=root/'revision-chain'/'generic.log'
            with path.open('wb') as stream:
                stream.truncate(64*MIB+1)
            store=Artifacts(root)
            with self.assertRaisesRegex(ValueError,'reader bound'):
                store.read('revision-chain/generic.log')
            # Even summary paths do not silently relax explicit generic reads.
            with self.assertRaisesRegex(ValueError,'reader bound'):
                store.read(store.summary_member,limit=4)


if __name__=='__main__':unittest.main()
