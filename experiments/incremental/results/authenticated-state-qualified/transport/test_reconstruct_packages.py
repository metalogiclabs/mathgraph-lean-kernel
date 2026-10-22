import hashlib
import io
import json
import lzma
from pathlib import Path, PurePosixPath
import tarfile
import tempfile
import unittest
import zipfile

import reconstruct_packages as reader


SOURCE='a'*40
RUN=7654321


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class Fixture:
    def __init__(self,root,entries=None,tar_entries=None,padding=b''):
        self.root=Path(root)
        self.index=self.root/'index.zip'
        self.parts=self.root/'parts'
        self.parts.mkdir()
        raw=b'genuine fixture bytes\n'
        names=['artifacts/a','artifacts/b']
        self.entries=entries or [dict(path=n,sha256=digest(raw),bytes=len(raw)) for n in names]
        buffer=io.BytesIO()
        with tarfile.open(fileobj=buffer,mode='w') as archive:
            for name,kind,value in (tar_entries or [('artifacts/a','file',raw),('artifacts/b','link','artifacts/a')]):
                info=tarfile.TarInfo(name)
                if kind=='file':
                    info.size=len(value)
                    archive.addfile(info,io.BytesIO(value))
                elif kind=='link':
                    info.type=tarfile.LNKTYPE;info.linkname=value
                    archive.addfile(info)
                elif kind=='symlink':
                    info.type=tarfile.SYMTYPE;info.linkname=value
                    archive.addfile(info)
        self.raw_archive=lzma.compress(buffer.getvalue()+padding)
        self.part=dict(path='artifact-packages/compact.tar.xz.part00',sha256=digest(self.raw_archive),bytes=len(self.raw_archive))
        package=dict(format='tar.xz',sha256=digest(self.raw_archive),bytes=len(self.raw_archive),ordered_parts=[self.part],files=sorted((e['path'] for e in self.entries),key=PurePosixPath))
        self.manifest=dict(schema='mathgraph.authenticated-state-artifact-packages.v1',source_sha=SOURCE,
                           github_run_id=str(RUN),github_run_attempt='1',all_files=self.entries,
                           archives={'compact':package,'full':dict(package)})
        self.run=dict(id=RUN,head_sha=SOURCE,status='completed',conclusion='success',run_attempt=1)
        self.part_name='authenticated-state-compact-00-'+SOURCE
        self.part_zip=self.parts/(self.part_name+'.zip')
        with zipfile.ZipFile(self.part_zip,'w') as z:z.writestr('compact.tar.xz.part00',self.raw_archive)
        self.metadata={'artifacts':[]}
        self.write_index()

    def record(self,path,name,artifact_id):
        return dict(id=artifact_id,name=name,size_in_bytes=path.stat().st_size,
                    digest='sha256:'+reader.sha(path),expired=False,
                    workflow_run=dict(head_sha=SOURCE,id=RUN))

    def write_index(self):
        with zipfile.ZipFile(self.index,'w') as z:
            z.writestr('manifest.json',json.dumps(self.manifest))
            z.writestr('REPLAY.txt','fixture only')
        self.metadata['artifacts']=[self.record(self.index,'authenticated-state-index-'+SOURCE,100),
                                    self.record(self.part_zip,self.part_name,101)]

    def run_reader(self):
        return reader.reconstruct(source=SOURCE,run_id=RUN,run=self.run,artifacts=self.metadata,
                                  index_zip=self.index,parts_dir=self.parts,out=self.root/'output')


class Tests(unittest.TestCase):
    def fixture(self,**kw):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        return Fixture(temp.name,**kw)

    def test_positive_hardlink_copy(self):
        f=self.fixture();p=f.run_reader()
        self.assertTrue(p['passed']);self.assertEqual(p['files_verified'],2)
        a=f.root/'output/artifacts/a';b=f.root/'output/artifacts/b'
        self.assertEqual(a.read_bytes(),b.read_bytes())
        self.assertNotEqual(a.stat().st_ino,b.stat().st_ino)
        self.assertEqual(len(p['hardlinks_materialized_as_copies']),1)

    def test_provider_digest_mismatch(self):
        f=self.fixture();f.metadata['artifacts'][1]['digest']='sha256:'+'0'*64
        with self.assertRaisesRegex(ValueError,'provider ZIP SHA256'):f.run_reader()

    def test_pathlib_component_sort_used_by_actual_workflow(self):
        a='artifacts/authenticated-state/summary.json'
        b='artifacts/authenticated-state-independent/summary.json'
        self.assertNotEqual(sorted([a,b]),sorted([a,b],key=PurePosixPath))
        raw=b'genuine fixture bytes\n'
        entries=[dict(path=n,sha256=digest(raw),bytes=len(raw)) for n in [a,b]]
        f=self.fixture(entries=entries,tar_entries=[(a,'file',raw),(b,'link',a)])
        self.assertTrue(f.run_reader()['passed'])

    def test_unsuccessful_run(self):
        f=self.fixture();f.run['conclusion']='failure'
        with self.assertRaisesRegex(ValueError,'did not succeed'):f.run_reader()

    def test_foreign_source(self):
        f=self.fixture();f.metadata['artifacts'][0]['workflow_run']['head_sha']='b'*40
        with self.assertRaisesRegex(ValueError,'foreign provider'):f.run_reader()

    def test_missing_part(self):
        f=self.fixture();f.metadata['artifacts'].pop()
        with self.assertRaisesRegex(ValueError,'missing provider part'):f.run_reader()

    def test_inner_part_digest(self):
        f=self.fixture();f.manifest['archives']['compact']['ordered_parts'][0]['sha256']='0'*64;f.write_index()
        with self.assertRaisesRegex(ValueError,'inner part identity'):f.run_reader()

    def test_whole_archive_digest(self):
        f=self.fixture();f.manifest['archives']['compact']['sha256']='0'*64;f.write_index()
        with self.assertRaisesRegex(ValueError,'whole archive identity'):f.run_reader()

    def test_unreported_member(self):
        f=self.fixture(tar_entries=[('artifacts/a','file',b'genuine fixture bytes\n'),('artifacts/extra','file',b'x')])
        with self.assertRaisesRegex(ValueError,'unexpected tar member'):f.run_reader()

    def test_changed_member_bytes(self):
        f=self.fixture(tar_entries=[('artifacts/a','file',b'changed fixture bytes\n')])
        with self.assertRaisesRegex(ValueError,'tar member SHA256'):f.run_reader()

    def test_path_escape(self):
        f=self.fixture(entries=[dict(path='artifacts/../escaped',sha256=digest(b'x'),bytes=1)],tar_entries=[('artifacts/../escaped','file',b'x')])
        with self.assertRaisesRegex(ValueError,'unsafe path'):f.run_reader()

    def test_symlink(self):
        f=self.fixture(tar_entries=[('artifacts/a','symlink','/etc/passwd')])
        with self.assertRaisesRegex(ValueError,'symlink/special'):f.run_reader()

    def test_unsafe_hardlink(self):
        f=self.fixture(tar_entries=[('artifacts/a','link','artifacts/not-present')])
        with self.assertRaisesRegex(ValueError,'earlier verified file'):f.run_reader()

    def test_missing_member(self):
        f=self.fixture(tar_entries=[('artifacts/a','file',b'genuine fixture bytes\n')])
        with self.assertRaisesRegex(ValueError,'cover exact package'):f.run_reader()

    def test_duplicate_member(self):
        f=self.fixture(tar_entries=[('artifacts/a','file',b'genuine fixture bytes\n')]*2)
        with self.assertRaisesRegex(ValueError,'duplicate tar member'):f.run_reader()

    def test_nonzero_trailer(self):
        f=self.fixture(padding=b'FORGED HIDDEN TRAILER')
        with self.assertRaisesRegex(ValueError,'nonzero bytes after tar'):f.run_reader()

    def test_output_refuses_overwrite(self):
        f=self.fixture();(f.root/'output').mkdir()
        with self.assertRaisesRegex(ValueError,'already exists'):f.run_reader()

    def test_duplicate_json_key(self):
        with self.assertRaisesRegex(ValueError,'duplicate JSON key'):reader.load('{"x":1,"x":2}')


if __name__=='__main__':unittest.main(verbosity=2)
